---
title: ServiceHost boundary | bt_api_binance
---

# Binance provider and ServiceHost boundary

The Binance package provides direct REST/WebSocket feeds, typed exchange data, and BinanceDirectClient. PluginLoader calls register_plugin(registry) to register those direct feeds with the bt_api provider registry; importing the package does not auto-register a gateway adapter.

The legacy `BinanceGatewayAdapter` runtime wrapper and export have been removed. The standalone `BinanceDirectClient` and Binance account-session provider remain available through their direct APIs; neither by itself creates an integrated ServiceHost market/account projection. Managed live writes must be issued through ServiceExecutionSession and service-v2 after a provider has been integrated with the host. `BinanceDirectClient` remains a direct exchange client, not a ServiceHost session.

See the README for direct BtApi usage and the feed/container references for package-level interfaces.
