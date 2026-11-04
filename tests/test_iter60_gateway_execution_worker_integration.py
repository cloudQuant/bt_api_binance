"""Iteration 60: the real Gateway worker publishes Binance execution observations.

``GatewayAccountSessionWorker`` + ``GatewayExecutionEventPublisher`` + a
temporary ``GatewayEventJournal`` drive ``BinanceUsdMAccountSessionProvider``
over a fake transport: a Base strategy-prefixed clientOrderId routes the order
and its fill to that strategy's execution stream, a higher fee after a restart
is a fee correction (a new event), a lower fee is refused by the Gateway and
redelivered unconfirmed, and a further restart publishes nothing new.
Evidence: INTEGRATION_SIM (local SQLite, fake venue); no network or account.
"""

from __future__ import annotations

import pytest

pytest.importorskip("bt_api_gateway")

from bt_api_base.execution_row_observation_protocol import (  # noqa: E402
    EXECUTION_TRADE_EVENT_KIND,
    execution_observation_from_event,
    strategy_client_order_id,
    strategy_client_order_prefix,
)
from test_iter60_gateway_execution_observations import (  # noqa: E402
    SECRET,
    Clock,
    FakeIssuer,
    FakeUsdmVenue,
    account_key,
    order_row,
    scope,
    trade_row,
)

from bt_api_binance.account_session_provider import (  # noqa: E402
    BinanceUsdMAccountSessionProvider,
    BinanceUsdMApiCredentials,
)
from bt_api_binance.gateway_execution_observations import RESOURCE  # noqa: E402
from bt_api_gateway import GatewayCommandKind, GatewayEventJournal, GatewayPrincipal  # noqa: E402
from bt_api_gateway.account_session_worker import (  # noqa: E402
    GatewayAccountSessionWorker,
    GatewayAccountSessionWorkerError,
)
from bt_api_gateway.execution_event_publisher import (  # noqa: E402
    GatewayExecutionEventPublisher,
    GatewayExecutionScopePolicy,
)
from bt_api_gateway.session_guard import LocalAccountSessionGuard  # noqa: E402

ACCOUNT_SCOPE = "account:binance-demo"
STATE_SCOPE = "strategy:account-facts"
EXEC_A = "exec:strategy-a"
UNATTRIBUTED = "exec:unattributed"


class Deployment:
    def __init__(self, tmp_path, venue, clock, issuer):
        self.tmp_path, self.venue, self.clock, self.issuer = tmp_path, venue, clock, issuer
        (tmp_path / "guards").mkdir(exist_ok=True)
        self.worker = None
        self.provider = None
        self.journal = None

    def start(self):
        """A fresh Gateway process: new provider, worker, generation; same files."""

        if self.worker is not None:
            self.worker.close()
        self.clock.advance(2.0)
        self.journal = GatewayEventJournal(self.tmp_path / "gateway.db", clock=lambda: self.clock.wall)
        key = account_key()
        self.provider = BinanceUsdMAccountSessionProvider(
            BinanceUsdMApiCredentials("fixture-api-key", SECRET),
            transport=self.venue,
            wall_clock=lambda: self.clock.wall,
            monotonic_clock=lambda: self.clock.mono,
            execution=scope(self.issuer),
        )
        publisher = GatewayExecutionEventPublisher(
            self.journal,
            account_key=key,
            journal_account_scope=ACCOUNT_SCOPE,
            policy=GatewayExecutionScopePolicy.for_strategies(
                {"strategy-a": EXEC_A}, unattributed_scope=UNATTRIBUTED
            ),
        )
        self.worker = GatewayAccountSessionWorker(
            self.provider,
            self.journal,
            account_key=key,
            journal_account_scope=ACCOUNT_SCOPE,
            state_scope=STATE_SCOPE,
            guard=LocalAccountSessionGuard(
                self.tmp_path / "guards", key.account_key_id, "gateway-owner"
            ),
            required_coverage=(RESOURCE,),
            clock=lambda: self.clock.wall,
            monotonic_clock=lambda: self.clock.mono,
            execution_publisher=publisher,
        )
        self.worker.start()
        return self.worker

    def events(self, scope_name):
        principal = GatewayPrincipal(
            principal_id="reader",
            account_scopes=frozenset({ACCOUNT_SCOPE}),
            strategy_scopes=frozenset({scope_name}),
            allowed_kinds=frozenset({GatewayCommandKind.READ}),
        )
        batch = self.journal.read_after(principal, ACCOUNT_SCOPE, scope_name, cursor=None, limit=100)
        return [
            (event.kind, execution_observation_from_event(event.kind, event.event_id, event.payload))
            for event in batch.events
        ]


def test_binance_fills_route_by_strategy_prefix_with_fee_corrections_and_restarts(tmp_path):
    clock = Clock()
    venue = FakeUsdmVenue(clock=clock)
    prefix = strategy_client_order_prefix("strategy-a")
    # The id a prefixed order-entry owner sends: venue grammar-valid (Base v2).
    strategy_id = strategy_client_order_id("strategy-a", "ab" * 32)
    assert strategy_id.isalnum() and len(strategy_id) <= 32
    venue.add_order(order_row(1001, client=strategy_id))
    venue.trades.append(trade_row(5001, 1001, commission="0.02"))
    venue.add_order(order_row(1002, client="web_manual_order"))
    venue.trades.append(trade_row(5002, 1002, commission="0.01"))
    gateway = Deployment(tmp_path, venue, clock, FakeIssuer())

    worker = gateway.start()
    result = worker.publish_execution_events()
    assert (result.appended, result.duplicates, result.unattributed_dropped) == (4, 0, 0)
    stream_a = gateway.events(EXEC_A)
    assert [observation.order.client_order_id for _kind, observation in stream_a[:1]] == [
        strategy_id
    ]
    (_k, order_a), (trade_kind, fill_a) = stream_a
    assert trade_kind == EXECUTION_TRADE_EVENT_KIND
    assert fill_a.trade.order_id == order_a.order.order_id and fill_a.fee == "0.02"
    assert len(gateway.events(UNATTRIBUTED)) == 2  # the manual order is not strategy A's
    assert worker.execution_status == "published"
    assert worker.publish_execution_events().appended == 0  # confirmed: nothing pending

    # Restart; the venue now reports a higher fee for the same fill.
    venue.trades[0]["commission"] = "0.03"
    worker = gateway.start()
    result = worker.publish_execution_events()
    assert (result.appended, result.duplicates) == (1, 3)
    stream_a = gateway.events(EXEC_A)
    assert len(stream_a) == 3
    correction = stream_a[2][1]
    assert correction.trade.trade_id == fill_a.trade.trade_id and correction.fee == "0.03"

    # Restart; a lower fee is reported as-is, refused by the Gateway, not confirmed.
    venue.trades[0]["commission"] = "0.025"
    worker = gateway.start()
    with pytest.raises(GatewayAccountSessionWorkerError) as refused:
        worker.publish_execution_events()
    assert refused.value.code == "EXECUTION_FEE_REGRESSED"
    generation = worker.session_generation
    redelivered = gateway.provider.read_execution_observations(
        generation=generation, timeout=2.0, limit=1000
    )
    assert any(getattr(item, "fee", None) == "0.025" for item in redelivered)
    worker.maintain()
    assert worker.execution_status == "failed:EXECUTION_FEE_REGRESSED"
    assert len(gateway.events(EXEC_A)) == 3

    # The venue is consistent again: a restart re-publishes nothing new.
    venue.trades[0]["commission"] = "0.03"
    worker = gateway.start()
    result = worker.publish_execution_events()
    assert (result.appended, result.duplicates) == (0, 4)
    assert len(gateway.events(EXEC_A)) == 3 and len(gateway.events(UNATTRIBUTED)) == 2
    worker.close()
