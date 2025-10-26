## 🎯 Objective

You are analyzing live-captured **Blue Protocol: Star Resonance (BPSR)** packets from the in-game **Trading Center UI**. The binary data was extracted from Wireshark (clientbound TCP stream) and saved as raw `.bin`.

Your job is to **parse, decompress, and decode** these packets into structured JSON with a focus on market listings: item names, IDs (if available), quantities, and Luno prices.

---

## 📜 Ground Truth (Manual Session Log)

This `.bin` was captured during the following real-game interaction:

1. Opened **Trading Center** in-game.
2. It loaded into the **Sell** tab.
3. Clicked **Withdraw All** (collected sold items — possibly skill books).
4. Accidentally opened **Notice** tab, then navigated to **Purchase > Follow**.
5. Clicked into an item listing:  
   **Arcane Seal - Attack** with the following observed entries:
   - 3 units for 28,688 Luno
   - 1 unit for 43,152 Luno
   - 7 units for 44,640 Luno
6. Refreshed the listing once — same entries appeared.

> ✅ Use this info to cross-check whether your decoded data reflects the real item quantities + Luno prices.

---

## 📂 Project Structure

```

/bpsr_labs/
├── ref/
│   ├── bpsr-logs/                    # Rust DPS meter (original decoder impl)
│   ├── StarResonanceData/           # Datamined schemas, item mappings, etc.
│   ├── bpsr_packet_structure.png    # Visual guide for frame layout
│   ├── bpsr-logs-ARCHITECTURE.md    # bpsr-logs breakdown
│   ├── KICKOFF.md                   # Initial agent instruction set
│   ├── message.txt                  # Example of a decoded payload
│   └── server_to_client.bin         # 🔥 Your input — raw TCP fragment binary
├── bpsr_labs/                       # Python decoding package
│   └── packet_decoder/
│       ├── cli/
│       └── decoder/
├── data/
│   ├── schemas/
│   ├── captures/
│   └── game-data/
├── docs/
├── examples/
├── .local/docs/proj/
└── tests/

````

---

## 📦 Packet Format (verify against source)

Use this as a starting point only — **confirm with code**.

| Offset | Size  | Field         | Notes |
|--------|-------|---------------|-------|
| 0–3    | u32   | `frag_len`    | Big-endian length |
| 4–5    | u16   | `packet_type` | High bit = zstd compression |
| 6–13   | u64   | `service_uid` | e.g. `0x0000000063335342` (combat) |
| 14–17  | u32   | `stub_id`     | Often unused |
| 18–21  | u32   | `method_id`   | Maps to protobuf |
| 22+    | var   | `frag_payload`| May be zstd-compressed |

---

## 📌 Task Breakdown

1. **Parse and iterate** over `server_to_client.bin`:
   - Extract frames using the format above.
   - Decompress if needed.
   - Retain key fields: `service_uid`, `method_id`, `packet_type`.

2. **Determine protobuf type**:
   - Use `method_id`/`service_uid` as clues.
   - Search inside `ref/` for `.proto` or `.rs` that map to these IDs.
   - Validate decoding against `message.txt` or observed structures.

3. **Decode trade-related packets**, especially:
   - Items for sale
   - Item ID / name
   - Quantity
   - Luno price
   - Any timestamps / metadata (if present)

---

## 🧩 Reference Candidates

Likely proto messages might include:

- `ExchangeSellItem`
- `ExchangeRecord`
- `MarketListResponse`
- `ShopItemList`, `TradeItem`
- Possibly `FollowedItemListResponse`

Item names may not be directly present — use `item_id` as a placeholder if needed. You can optionally cross-reference against `StarResonanceData`.

---

## ✅ Final Output Format (Required)

Emit as structured **JSON** or **TSV**. Minimum fields per listing:

```json
{
  "item_id": 123456,
  "item_name": "Arcane Seal - Attack",  // optional if only ID available
  "price_luno": 28688,
  "quantity": 3
}
````

You may aggregate multiple results — just ensure they're **decoded, not fabricated**.

---

## 🔍 Additional Expectations

* Print/log suspected proto message types for each decoded packet.
* Write fallback logic for unknown method IDs.
* Optionally create `decode_trade_packets.py` in the root to encapsulate your logic.

---

## 🛠 Hints

* Decompression + framing helpers may already exist in `ref/bpsr-logs`.
* Use `bpsr_packet_structure.png` and `message.txt` to validate offsets and structure.
* If you decode a match (e.g. 3× Arcane Seal @ 28688), dump all other listings in the same flow.

---

## ❌ Do NOT

* ❌ Do not hard-code values based on the observed log.
* ❌ Do not assume every method ID maps 1:1 to a protobuf — validate by decoding.
* ❌ Do not silently skip malformed or unknown packets — log them.

---

## 🧠 Final Note

This is a **live decoding + verification task** grounded in real gameplay. Think critically, use provided code as inspiration, and generalize the pipeline so it can scale to other `.bin` captures later.