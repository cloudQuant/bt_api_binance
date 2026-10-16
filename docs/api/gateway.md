---
title: ServiceHost boundary | bt_api_binance
---

# Binance provider and ServiceHost boundary

The Binance package provides direct REST/WebSocket feeds, typed exchange data, and BinanceDirectClient. PluginLoader calls register_plugin(registry) to register those direct feeds with the bt_api provider registry; importing the package does not auto-register a gateway adapter.

The legacy `BinanceGatewayAdapter` implementation and package export remain in the source tree, but are retired and unsupported. This package does not currently provide an integrated ServiceHost gateway bridge. Its direct provider API does not by itself create a managed ServiceHost market/account projection. Managed live writes must be issued through ServiceExecutionSession and service-v2 after the provider has been integrated with the host. The standalone BinanceDirectClient remains a direct exchange client and is not a ServiceHost session.

See the README for direct BtApi usage and the feed/container references for package-level interfaces.
