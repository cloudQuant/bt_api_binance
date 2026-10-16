# Iteration 10 DIM06 Binance TIF guard (R1)

Date: 2026-10-16. Repository: bt_api/bt_api_binance, branch dev, baseline HEAD b438a277c92a22851a16be0be1a8c8ee9f852b79.

This narrow round adds a local LIMIT time-in-force guard in src/bt_api_binance/feeds/rest_trade.py. The verified matrix is endpoint-scoped: SPOT accepts GTC/IOC/FOK; the USDⓈ-M SWAP /fapi/v1/order path accepts GTC/IOC/FOK/GTX/GTD/RPI. SWAP GTD requires a native goodTillDate or good_till_date value and serializes it; the current typed OrderRequest cannot provide that field, so the mapper path fails closed. Other asset families and market orders are not broadened by this change.

Root's fixed-source joint SDK check included this package's canonical production imports and terminal synthetic request spy: 21 cases passed in 1.36s, Python/pytest exit 0, no warnings, empty stderr, 221 source pins unchanged, and the four bound repository HEADs unchanged. The node breakdown is 8 supported Binance TIF parameterizations, 9 local rejects, one market omission, one valid native GTD case, one OKX rejection, and one OKX valid-neighbor case. Evidence is under dim06-tif-guards-20261016; the preserved spec.json retains its creation-time UNEXECUTED evidence-level field, while result.json and stdout.log record the completed run.

Evidence is synthetic/local only. No exchange, account, credentials, or real provider request was used. This package change can be committed independently as the exact two-path scope below; no package-local test or separate QA was run.

- src/bt_api_binance/feeds/rest_trade.py — SHA-256 19d0c782ad440a3d04853fa269595c3b73050a0f1922b3c4a899652f00cf8f86
- docs/development/iteration10-dim06-tif-guards-r1.md — this round record
- Proposed commit subject: fix(binance): reject unsupported limit TIF locally
- Commit status: not committed; Root should recheck the scoped diff and stage only these two paths.