# Official editor parameter names

Names and controls from Hotone Ampero Editor V1.6.0, Mini-specific `Resource/Ampero/File/algorithm_50.xml`. Compatible with Mini firmware V2.2. These are editor definitions, not new live write verification. Existing live statuses stay intact.

[Official Windows package](https://res.hotoneaudio.com/prod/support/Ampero%20Editor%20Setup%20V1.6.0%20for%20Windows.1784621019036.zip) | [Compatibility listing](https://www.hotoneaudio.com/support/3?tid=1&pid=92)

## Conflicts and encoding cautions

- Classic PS Range is an enum 0-5, not the manual's 0-100. Never write 6.
- Trem Jet FX3: XML gives both Trm Rate and Flg Sync ID 5. Pedal-proven Trm Rate p4, Flg Sync p5 and Trm Sync p6 win.
- CAB code 0 Hi Cut duplicates Step=1 and Step=10. Raw editor attributes are ambiguous; no API bound is inferred from that step.
- Marshell 50 p2: checked map says Master, editor says Output. Keep Master pending a screen check.
- Display bounds may be transformed by valueType. They are not automatically safe raw API bounds. CAB cuts are packed; ms/Hz and signed display values need existing wire encoding.
- Sound Clone slots take imported tone files. Prior silent tests describe loaded contents, not unusable placeholders.
- Black Twin names were confirmed on the pedal screen on October 6, 2026.

## AMP, screen order

### Tweed Lux (code 0)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |

### Baseman Norm (code 1)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Black Twin (code 2)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Master | write-verified | 0.0 to 100.0 |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Middle | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |
| 5 | Bright | address-confirmed-only | 0=Off, 1=On |

### Voxy 30HW Norm (code 3)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone Cut | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bright | address-confirmed-only | 0=Off, 1=On |

### Jazz Clean (code 4)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Bright | write-verified | 0=Off, 1=On |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Middle | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |

### Emperor Clean (code 5)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Superstar Clean (code 6)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Glacian Clean (code 7)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |
| 5 | Bright | address-confirmed-only | 0=Off, 1=On |

### Tweed Prince (code 8)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |

### Black Prince (code 9)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Output | write-verified | 0.0 to 100.0 |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Treble | editor-defined | 0.0 to 100.0 |

### Baseman Bright (code 48)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Voxy 30HW TB (code 49)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone Cut | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |
| 5 | Char | address-confirmed-only | 0=Cool, 1=Hot |

### Emperor Drive (code 50)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Superstar Drive (code 51)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Drive | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 45 (code 52)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 45+ (code 53)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 45 Jump (code 54)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 50 (code 55)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 50+ (code 56)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Marshell 50 Jump (code 57)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Output | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Hot Kitty Drive (code 58)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Edge | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Messe IIC+ 1 (code 59)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Messe IIC+ 2 (code 60)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Messe IIC+ 3 (code 61)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Soloist 100 Crunch (code 62)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Marshell 800 (code 63)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Fryman B1 (code 64)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Fryman B2 (code 65)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Glacian Drive (code 66)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Marshell 900 (code 96)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Dizzle VH B (code 97)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Dizzle VH S (code 98)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Engle Saga 1 (code 99)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Engle Saga 2 (code 100)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Fryman HB (code 101)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Fryman HB+ (code 102)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Eddie 51 (code 103)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Soloist 100 Lead (code 104)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Messe IV Lead 1 (code 105)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Messe IV Lead 2 (code 106)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Messe IV Lead 3 (code 107)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | address-confirmed-only | 0.0 to 100.0 |
| 1 | Presence | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Middle | address-confirmed-only | 0.0 to 100.0 |
| 5 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Tangerine R100 (code 108)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Master | write-verified | 0.0 to 100.0 |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Middle | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |

### Rector Dual V (code 109)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Rector Dual M (code 110)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Dizzle VH+ B (code 111)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Dizzle VH+ S (code 112)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Boger XT Blue M (code 113)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Presence | write-verified | 0.0 to 100.0 |
| 2 | Master | write-verified | 0.0 to 100.0 |
| 3 | Bass | write-verified | 0.0 to 100.0 |
| 4 | Middle | write-verified | 0.0 to 100.0 |
| 5 | Treble | write-verified | 0.0 to 100.0 |

### Alchemy Pre (code 160)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Bright | address-confirmed-only | Switch |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Middle | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |

### Ampage Classic (code 161)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | write-verified | 0.0 to 100.0 |
| 1 | Bass | write-verified | 0.0 to 100.0 |
| 2 | Middle | write-verified | 0.0 to 100.0 |
| 3 | Midrange | write-verified | 0=220Hz, 1=450Hz, 2=800Hz, 3=1.6kHz, 4=3kHz |
| 4 | Treble | write-verified | 0.0 to 100.0 |
| 5 | Master | write-verified | 0.0 to 100.0 |

### Ampage Flip (code 162)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Bass | write-verified | 0.0 to 100.0 |
| 2 | Treble | write-verified | 0.0 to 100.0 |

### Voxy Bass (code 163)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Bass | write-verified | 0.0 to 100.0 |
| 2 | Treble | write-verified | 0.0 to 100.0 |

### Messe Bass 400 (code 164)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Master | write-verified | 0.0 to 100.0 |
| 2 | Bass | write-verified | 0.0 to 100.0 |
| 3 | Middle | write-verified | 0.0 to 100.0 |
| 4 | Treble | write-verified | 0.0 to 100.0 |

### Acoustic Preamp 1 (code 192)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone | write-verified | 0.0 to 100.0 |
| 2 | Balance | write-verified | 0.0 to 100.0 |
| 3 | EQ Freq | write-verified | 0.0 to 100.0 |
| 4 | EQ Q | write-verified | 0.0 to 100.0 |
| 5 | EQ Gain | address-confirmed-only | 0.0 to 100.0 |

### Acoustic Preamp 2 (code 193)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | write-verified | 0.0 to 100.0 |
| 1 | Tone | write-verified | 0.0 to 100.0 |
| 2 | Balance | write-verified | 0.0 to 100.0 |
| 3 | EQ Freq | write-verified | 0.0 to 100.0 |
| 4 | EQ Q | write-verified | 0.0 to 100.0 |
| 5 | EQ Gain | address-confirmed-only | 0.0 to 100.0 |

### Match 30 Clean (code 194)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Volume | address-confirmed-only | 0.0 to 100.0 |
| 1 | Tone Cut | address-confirmed-only | 0.0 to 100.0 |
| 2 | Master | address-confirmed-only | 0.0 to 100.0 |
| 3 | Bass | address-confirmed-only | 0.0 to 100.0 |
| 4 | Treble | address-confirmed-only | 0.0 to 100.0 |

### Sound Clone 6 (code 195)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | editor-defined | 0.0 to 100.0 |
| 1 | VOL | editor-defined | 0.0 to 100.0 |
| 2 | Bass | editor-defined | 0.0 to 100.0 |
| 3 | Middle | editor-defined | 0.0 to 100.0 |
| 4 | Treble | editor-defined | 0.0 to 100.0 |

### Sound Clone 7 (code 196)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | editor-defined | 0.0 to 100.0 |
| 1 | VOL | editor-defined | 0.0 to 100.0 |
| 2 | Bass | editor-defined | 0.0 to 100.0 |
| 3 | Middle | editor-defined | 0.0 to 100.0 |
| 4 | Treble | editor-defined | 0.0 to 100.0 |

### Sound Clone 8 (code 197)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | editor-defined | 0.0 to 100.0 |
| 1 | VOL | editor-defined | 0.0 to 100.0 |
| 2 | Bass | editor-defined | 0.0 to 100.0 |
| 3 | Middle | editor-defined | 0.0 to 100.0 |
| 4 | Treble | editor-defined | 0.0 to 100.0 |

### Sound Clone 9 (code 198)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | editor-defined | 0.0 to 100.0 |
| 1 | VOL | editor-defined | 0.0 to 100.0 |
| 2 | Bass | editor-defined | 0.0 to 100.0 |
| 3 | Middle | editor-defined | 0.0 to 100.0 |
| 4 | Treble | editor-defined | 0.0 to 100.0 |

### Sound Clone 10 (code 199)

| p | Name | Live status | Editor control |
| --- | --- | --- | --- |
| 0 | Gain | editor-defined | 0.0 to 100.0 |
| 1 | VOL | editor-defined | 0.0 to 100.0 |
| 2 | Bass | editor-defined | 0.0 to 100.0 |
| 3 | Middle | editor-defined | 0.0 to 100.0 |
| 4 | Treble | editor-defined | 0.0 to 100.0 |

## All blocks

Complete ordered controls, defaults, selector labels and source attributes for all 317 models are in [editor-parameters.json](editor-parameters.json). The merged [param-map.json](param-map.json) preserves live evidence and adds separate editor definitions. CAB retains its shared live template plus per-model editor definitions.
