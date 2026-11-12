# Data the policies read

`Current.user` is `nil` for a signed-out visitor. Otherwise it is a `User`:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | |
| `roles` | array of strings | `admin`, `editor`, `external`, `member`; more roles are added over time |
| `team_ids` | array of strings | |
| `suspended?` | boolean | `true` only for suspended accounts |

`Document`:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | |
| `owner_id` | string | |
| `team_id` | string | |
| `published` | boolean | |
| `confidential` | boolean | |
| `locked_by` | string or `nil` | the user ID holding the edit lock, `nil` when unlocked |
