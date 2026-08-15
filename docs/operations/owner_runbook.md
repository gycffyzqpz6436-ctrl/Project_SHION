# Project SHION Owner Startup / Shutdown Runbook

最終実機確認日: 2026-08-13

このRunbookはOwnerの日常利用向けです。コマンドは、次の現在の実装と実配置を監査して確認したものだけを記載しています。

- Source repository: `C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main`
- Runtime data root: `D:\AI\Project_SHION`
- Windows / NVIDIA GeForce RTX 5070 12 GB
- SHION Chat: `127.0.0.1:8765`
- SHION Voice: `127.0.0.1:8766`

Stable Diffusionについては、モデルと過去の生成物は存在しますが、現在起動可能なbackend/venv/entry pointはありません。SHION Chatにも未統合です。詳細は「Image Generation / Stable Diffusion」を参照してください。

## 1. 通常起動

通常はPowerShellを1つ開き、Chatだけを起動します。SHION Chatの画面を開くとVoice metadataが読み込まれ、専用Voice serviceが必要に応じて自動起動します。Voiceを先に手動起動する必要はありません。

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
$env:SHION_DATA_ROOT = 'D:\AI\Project_SHION'
training\.venv\Scripts\python.exe app\server.py --model gemma4_12b_heretic_ja_v2_manual
```

コンソールに次が表示されるまで待ちます。

```text
SHION Web Chat: http://127.0.0.1:8765
```

ブラウザで開きます。

```text
http://127.0.0.1:8765/
```

画面上部が `Ready`、`Connected` になるまで送信しないでください。`History PERSISTENT` は、SQLite履歴が正常であることを示します。

### 起動モデルを選ぶ場合

上記はWorkspace Phase BでdefaultになったGemma 4 Heretic JA v2を明示しています。現在のallowlistから別モデルで開始する場合は、`--model` の値だけを置き換えます。既存Conversationに保存されたmodel metadataは変更しません。

```powershell
# Official Gemma 4 Owner Manual Test
training\.venv\Scripts\python.exe app\server.py --model gemma4_12b_it_manual

# Gemma 4 Heretic JA v2 Owner Manual Test
training\.venv\Scripts\python.exe app\server.py --model gemma4_12b_heretic_ja_v2_manual
```

`Owner Manual Test` や `Experimental` は正式SHION Base採用を意味しません。任意のmodel pathは指定できず、`app/model_registry.json` のaliasだけが使用できます。

## 2. Chat Only

### Web Chat

- venv: `training\.venv`
- working directory: repository root
- entry point: `app\server.py`
- bind: `127.0.0.1`
- port: `8765`
- URL: `http://127.0.0.1:8765/`

起動コマンドは通常起動と同じです。画像生成は起動しません。

注意: 現在のWeb UIは初期化時に `/api/voice/meta` を取得します。Chat側のVoice adapterは、その要求を受けると8766のVoice serviceをlazy起動します。そのため、ブラウザ版には「Voice processを絶対に起動しない」起動flagはありません。Voiceを使わなければTTS生成は行われませんが、Voice service自体は待機状態になります。

### 厳密なtext-only CLI

Voice serviceもWeb UIも起動しない既存手段は、次のCLIです。SQLite Conversation Historyとは別の一時的なCLI会話で、`--save-session` を付けない限りsessionを書き出しません。

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
training\.venv\Scripts\python.exe training\scripts\chat_local.py `
  --common training\configs\common.yaml `
  --model-config training\configs\shion_sft_exp_0001_ministral8b.yaml `
  --mode minimal
```

### Ready確認

別のPowerShellで実行します。

```powershell
Invoke-RestMethod 'http://127.0.0.1:8765/api/status' |
  Select-Object state, model_alias, history, voice
```

期待値:

- `state`: `Ready`
- `history.state`: `PERSISTENT`
- `model_alias`: 起動時に指定したalias
- `voice.state`: ブラウザでVoice初期化前は `AVAILABLE`

## 3. Chat + Voice

### 推奨: Chatから自動起動

通常起動コマンドだけを実行し、ブラウザでChatを開いてください。Chatは次の専用Pythonを使ってVoice serviceを自動起動します。

```text
D:\AI\Project_SHION\runtime\voice-venv\py310-cu128\Scripts\python.exe
```

実際に起動されるentry point:

```text
voice\server.py --port 8766
```

Voiceは `127.0.0.1:8766` のみにbindし、Chatは `http://127.0.0.1:8766` へHTTP接続します。Style-Bert-VITS2をChat processへimportしません。

### Voice Tuning Consoleを先に手動起動

Voice Model ManagerやTuning Consoleを先に使用する場合は、PowerShellをもう1つ開きます。

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
$env:SHION_DATA_ROOT = 'D:\AI\Project_SHION'
& 'D:\AI\Project_SHION\runtime\voice-venv\py310-cu128\Scripts\python.exe' voice\server.py --port 8766
```

Console URL:

```text
http://127.0.0.1:8766/
```

この状態でChatを起動すると、Chatは既存8766 serviceを検出して再利用します。この場合、Chatを停止しても手動起動したVoice Consoleは自動停止しません。

### Voice正常確認

```powershell
Invoke-RestMethod 'http://127.0.0.1:8766/api/meta' |
  Select-Object models, managed_models, presets
```

Chatだけを起動している状態で次を実行すると、Voice serviceのlazy起動も発生します。

```powershell
Invoke-RestMethod 'http://127.0.0.1:8765/api/voice/meta' |
  Select-Object state, approved_presets, developer_models
```

### SHION Default Voiceを使う

Owner承認済みの通常Voiceは次です。

```text
SHION Default
└─ Nene V3 (`nene_v3_candidate`)
   └─ Bright
```

1. SHION Chatを開く。新しいbrowser session、reload、server restart後も `SHION Default · Nene V3 · Bright` が自動選択される。
2. `Developer Voice` はOFFのままでよい。
3. 既存Assistant messageの `Read Aloud` を押す。
4. `Voice GENERATING` から `Voice READY` へ変わることを確認する。
5. 表示されたaudio controlで再生する。

Auto PlayをONにした場合もSHION Defaultが使われます。Browserのautoplay policyにより自動再生が拒否された場合だけ、audio controlを手動で押してください。

Nene V3のModel Registry entryは引き続き `nene_v3_candidate` で、Neutral / Bright / Softを保持します。`SHION Default` はModelとは別のOwner-approved presetです。Nene WhisperやJVNVを試聴する場合だけ `Developer Voice` を有効にします。

### Voice storage

```text
D:\AI\Project_SHION\models\voice
D:\AI\Project_SHION\runtime\voice
D:\AI\Project_SHION\runtime\voice-venv
D:\AI\Project_SHION\data\voice\models.json
D:\AI\Project_SHION\artifacts\voice
```

通常TTSは `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`local_files_only`相当の完全ローカル運用です。Hugging Face Preview/Downloadの明示操作だけが別の一時online policyを使用します。

### Phase G persistent Voice operations

Voice LabのPronunciation DictionaryでSHION用のoriginal/replacement、priority、enabled状態を管理します。`Test pronunciation`はTTS変換結果だけをpreviewし、Conversation表示文を変更しません。

Voice Artifact IndexはChatとVoice Labのartifactを再起動後も表示します。Replay、Retry、Restore Parameters、Favorite、DeleteをOwner操作できます。`WAV missing`はDB破損ではなくrecoverable状態です。Retryで新しいartifactを生成し、不要なmissing metadataは確認付きDeleteで削除してください。WAVは引き続きprivate runtime artifactでありGitへ追加しません。すべての生成・Retryは既存`GpuResourceGate`を通過します。

## 4. Image Generation / Stable Diffusion

### 現在の状態

監査で次を確認しました。

- model: `cagliostrolab/animagine-xl-4.0`
- fixed revision: `2b7c1b397761bf5bd3cc42e5b39ec99314a75a96`
- local path: `D:\AI\Project_SHION\models\image\animagine-xl-4.0-opt`
- pipeline metadata: `StableDiffusionXLPipeline`, Diffusers 0.29.0
- scheduler used in過去の実測: `EulerAncestralDiscreteScheduler`
- 過去の1024x1024生成Artifact: `D:\AI\Project_SHION\image_output\experimental`

一方、現在は次が存在しません。

- Stable Diffusion専用venv/runtime
- 起動可能な画像backend entry point
- AUTOMATIC1111 / Forge / ComfyUI server
- 画像backendのlistener/port
- SHION Chatから画像backendを呼ぶadapter

`training\.venv` にも `diffusers` は入っていません。SHION Chatの `image_generation` toolはdefault-disabledです。

したがって、現在使用可能なStable Diffusion server起動コマンドはありません。過去の単発生成実績だけを根拠に、現状を「統合済み」「起動可能」と扱ってはいけません。

- Stable Diffusion startup: **UNAVAILABLE / UNVERIFIED**
- SHION Chat integration: **NOT IMPLEMENTED**
- backend port: **NONE**

画像backendの再構築・launcher追加・Chat統合は別Owner Gateです。

## 5. Full SHION

現時点で日常的に同時利用可能なのは次です。

```text
SHION Chat
  -> Persistent Conversation DB
  -> lazy-start SHION Voice
  -> Browser
```

通常は次の順序だけで十分です。

1. SHION Chatを起動する。
2. ブラウザで `http://127.0.0.1:8765/` を開く。
3. 必要なときだけRead Aloudを使う。

Voice Consoleを個別に操作したい場合だけ、Voiceを先に起動してからChatを起動します。ChatとVoiceには「Voiceを先に起動しなければならない」という依存関係はありません。

Stable Diffusionは現在のFull SHION起動列へ含められません。

## 6. Browser Access

### PC local

```text
http://127.0.0.1:8765/
```

Chat backendは引き続き `127.0.0.1` のみにbindします。`0.0.0.0`、LAN直接公開、router port forwarding、Funnelは使用しません。

### Tailscale / iPhone

現在のTailscale Serve設定は読み取り専用監査で次の状態でした。

```text
https://pc.tail1098d4.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:8765
```

tailnet内のiPhone Safariから使うURL:

```text
https://pc.tail1098d4.ts.net/
```

SHION backendはloopbackから来るTailscale Serve proxy requestだけを、exact Host、Origin/Referer整合、Tailscale identity headerにより許可します。LAN端末から `192.168.x.x:8765` へ直接接続しても到達しません。

2026-08-13のPC側再検証では、TCP 443とTLS handshakeは成功しました。Chat停止中のGETは期待どおりupstream不在の `502 Bad Gateway` になりました。以前のcertificate/TCP timeoutはPC側では再現しませんでした。ただし、その時点でiPhoneはTailscale offlineだったため、iPhone Safariからの最新実機確認は **UNVERIFIED** です。

Tailscale設定はこのRunbook作成では変更していません。

## 7. 正常起動チェックリスト

画面または `/api/status` で確認します。

| Subsystem | 正常表示 | 現在の意味 |
|---|---|---|
| Conversation | `Ready` | model load完了、送信可能 |
| Connection | `Connected` | Browserから8765へ接続中 |
| History | `PERSISTENT` | SQLite conversation DB有効 |
| Voice | `AVAILABLE` | service利用可能または未生成 |
| Voice生成後 | `READY` | WAV生成・Artifact登録完了 |
| Image | `DISABLED` | 現在未統合。異常ではない |
| Vision | `DISABLED` | 現在未統合 |
| Memory | `READY` | Phase F Owner-controlled; automatic promotion OFF |

## Phase F Memory operations

Open **Memory** in the Workspace. `Remembered`, `Candidates`, `Temporary`, `Character`, `Archived`, and `Settings` are distinct review views. Direct additions are active Owner records. Explicit remember requests appear as candidates and require **Approve**. Edit, Pin, Archive, Reject, Restore, scope, and character actions are reversible; Hard Delete is permanent and requires typing `DELETE`.

If Memory reports unavailable, Chat intentionally continues without recalled context. Inspect the System subsystem status and application log for a generic failure class; do not paste private Memory content into logs or issue reports.

Before database maintenance, stop SHION and back up `%SHION_DATA_ROOT%\data\conversations\shion_chat.db` plus matching `-wal` and `-shm` files. Restore them only while SHION is stopped. Runtime databases and backups are private artifacts and must not enter Git.

## Context and generation diagnostics

Open an assistant message's **Details** action to inspect content-free generation telemetry. `History omitted` means older turns were excluded only from that model call; the Conversation and SQLite records remain intact. The Phase F formal default is 6,144 input tokens with 128/512/2,048/4,096 adaptive output budgets; future input-budget adjustment requires real-use telemetry and Owner review. `stop_reason` is `eos`, `max_tokens`, `repetition_guard`, `owner_stop`, or `generation_complete`.

High post-generation CUDA reservation alone does not authorize `empty_cache()` or model unload changes. Conditional CUDA cache release remains a future Performance Owner Gate; record idle/peak/post-settle VRAM and compare latency before proposing any policy change.

When an Owner challenge such as `？`, `違う`, a numeric correction, or a recheck request follows an Assistant answer, Message Details shows `Self-correction review: true` and `Decoding mode: verification_greedy`. The stored Conversation remains complete, but challenged Assistant claims are withheld from that independent review call. `Private channel filtered: true` means Gemma emitted a non-display channel that was excluded before persistence; private draft text is never included in Details.

### Port確認

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8765,8766 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

期待値:

- 8765: `127.0.0.1`
- 8766: Voice初期化後のみ `127.0.0.1`

PIDのprocess名だけを確認する場合:

```powershell
$listeners = Get-NetTCPConnection -State Listen -LocalPort 8765,8766 -ErrorAction SilentlyContinue
Get-Process -Id $listeners.OwningProcess | Select-Object Id, ProcessName, StartTime
```

これらは診断専用です。無差別な `taskkill python.exe` は行わないでください。

## 8. 停止方法

### 通常起動したChat + auto-start Voice

Chatを起動したPowerShellを選び、`Ctrl+C` を1回押します。

Chatのshutdown処理は、HTTP listenerを閉じ、model runtimeを解放し、Chat自身が起動したVoice subprocessを終了します。終了中は連打せず待ってください。

### Voice Consoleを手動で先に起動した場合

1. ChatのPowerShellで `Ctrl+C`。
2. Voice ConsoleのPowerShellで `Ctrl+C`。

手動Voice serviceはChatの所有processではないため、Chat停止だけでは終了しません。

### Text-only CLI

CLI内では `/exit`、またはPowerShellで `Ctrl+C` を使います。

### Stable Diffusion

現在停止対象となる画像backendはありません。

### 異常時

まずPort確認でPIDを特定してください。通常手順として全Python processを停止してはいけません。コンソールが失われ、特定PIDだけを止める必要がある場合も、CommandLineとPortの一致を確認してから行います。

## 9. 再起動

### Chatのみ

1. Chat PowerShellで `Ctrl+C`。
2. 8765が消えたことをPort確認する。
3. 通常起動コマンドを再実行する。

Conversation Historyは `D:\AI\Project_SHION\data\conversations\shion_chat.db` に保存され、正常な再起動では消えません。

### Voiceのみ

- 手動Voice Console: Voice PowerShellで `Ctrl+C` 後、Voice起動コマンドを再実行する。
- Chatがauto-startしたVoice: 専用Voice restart APIはありません。Chatを正常停止して再起動し、ブラウザを再読込するのが安全です。

Voice failureはConversation本文を削除しません。Retry Voiceは新しいattempt/Artifactを作り、以前のWAVを自動削除しません。

### Imageのみ

現在再起動可能な画像backendはありません。

### 全部

1. Chatを `Ctrl+C` で停止する。
2. 手動Voice Consoleが残っていれば `Ctrl+C` で停止する。
3. 8765/8766が消えたことを確認する。
4. 通常起動を実行する。
5. Browserを再読込する。

## 10. よくあるトラブル

### `port 8765 already in use`

診断:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8765 |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

対処:

- 既に開いているChat PowerShellへ戻り、そのinstanceを使う。
- 再起動が必要なら、そのPowerShellで `Ctrl+C`。
- 別のmodelを重複起動しない。
- 全Python processを無差別終了しない。

### SHIONがLoadingのまま

診断:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8765/api/status' | ConvertTo-Json -Depth 6
nvidia-smi
```

対処:

- 初回model load中は待つ。
- `nvidia-smi` で別のGPU processとVRAMを確認する。
- コンソールのmodel path、CUDA、OOM errorを確認する。
- Errorになった場合はChatを正常停止して再起動する。model downloadや`trust_remote_code`有効化で回避しない。

### Voice AVAILABLEだがRead Aloudできない

診断:

- `Voice` panelを開く。
- 通常欄に `SHION Default · Nene V3 · Bright` が表示されるか確認する。
- Nene Whisper/JVNV等のCandidate試聴なら `Developer Voice` が有効か確認する。

対処:

- 通常のNene V3 / BrightはDeveloper Voiceを使わずSHION Defaultから選ぶ。
- Nene Whisper/JVNV等はDeveloper Voiceから選ぶ。
- `Voice presetを選択してください` が出た場合はmodelを選択する。
- Read Aloudは永続化済みAssistant messageだけを対象にする。

### Voice ERROR

診断:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8766/api/meta' | ConvertTo-Json -Depth 6
nvidia-smi
```

対処:

- 8766がなければChatを再起動し、Browserを再読込する。
- 独立Voice Consoleを使う場合は専用venvの起動コマンドを再実行する。
- 一度に複数TTSを走らせない。実装はserialized TTS前提。
- Conversation本文は保持されるため、Voice復旧後に `Retry Voice` を使う。

### CUDA / VRAM不足

診断:

```powershell
nvidia-smi
```

RTX 5070は12,227 MiBです。GemmaとVoice同時常駐時はheadroomが小さくなります。

対処:

- Chat generation中にRead Aloudを重ねない。
- 不要な、正体を確認できるGPUアプリだけを通常操作で終了する。
- modelを切り替える前に現在のgeneration完了を待つ。
- OOM後はChat全体を正常再起動する。

### NeneがVoice一覧に出ない

診断:

```powershell
Test-Path 'D:\AI\Project_SHION\models\voice\commercial\ShizukaLab_Nene_VoicePalette_V3_0'
Get-Content 'D:\AI\Project_SHION\data\voice\models.json' -Raw
```

期待Registry ID:

- `nene_v3_candidate`
- `nene_whisper_candidate`

対処:

- Nene V3 / Brightは通常欄の `SHION Default` として表示される。Developer Voiceを有効にする必要はない。
- Nene WhisperやNene V3の別Styleを試聴する場合だけDeveloper Voiceを有効にする。
- Voice ConsoleのModel ManagerでRefreshする。
- 既存Nene directoryへ上書きコピーしない。
- ZIPを再展開・二重登録しない。

### Browserでaudioが再生されない

診断:

- `Voice READY` か確認する。
- audio controlが表示されるか確認する。
- Browserのautoplay制限messageを確認する。

対処:

- audio controlのPlayをOwnerがタップする。
- Auto Playはdefault OFF。Safari等では明示tapが必要な場合がある。
- Browserを再読込し、同じConversation HistoryからRead Aloudを再実行する。

### Conversation DB unavailable

診断:

```powershell
Test-Path 'D:\AI\Project_SHION\data\conversations\shion_chat.db'
Invoke-RestMethod 'http://127.0.0.1:8765/api/status' |
  Select-Object history
```

対処:

- `SHION_DATA_ROOT` が `D:\AI\Project_SHION` か確認する。
- D:がmountされ、Ownerにread/write権限があるか確認する。
- DBを削除・新規作成して回避しない。
- Backupを確保し、SQLite診断を別作業として行う。History unavailable時は明示的ephemeral fallbackとなり、永続履歴へ保存されない。

### Tailscaleから開けない

診断:

```powershell
tailscale status
tailscale serve status
curl.exe -vk --connect-timeout 8 https://pc.tail1098d4.ts.net/
```

対処:

- まずPC local URLがReadyか確認する。
- `tailscale serve status` が8765へのHTTPS proxyか確認する。
- iPhoneが同じtailnetでonlineか確認する。
- Chatを停止中なら502はupstream不在として正常。
- SHIONを`0.0.0.0`へ変更しない。HTTPへ恒久fallbackしない。Funnelを有効化しない。

### Stable Diffusion backendへ接続できない

現在は接続先backend自体が未構築です。これは一時的なnetwork errorではありません。

- model weightsと過去のArtifactは存在する。
- backend、venv、port、Chat adapterは存在しない。

推測したComfyUI/AUTOMATIC1111 commandを実行せず、画像runtime再構築のOwner Gateを作成してください。

## 11. Storage Map

### C: — Source / Git

```text
C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main
├─ app\                 # Chat server/UI/integration code
├─ voice\               # Voice integration/controller code
├─ training\            # Chat/training scripts and training/.venv
├─ tests\                # Tests
├─ docs\                 # Documentation
└─ .git\                 # Git metadata
```

モデル、DB、WAV、cache、購入License/READMEはGitへ入れません。

### D: — Private runtime data

```text
D:\AI\Project_SHION
├─ models
│  ├─ voice
│  │  ├─ commercial\ShizukaLab_Nene_VoicePalette_V3_0
│  │  ├─ jvnv
│  │  ├─ huggingface
│  │  └─ _incoming\ShizukaLab_Nene_VoicePalette_V3_0.zip
│  ├─ image\animagine-xl-4.0-opt
│  ├─ mistral
│  └─ experimental
├─ runtime
│  ├─ voice\Style-Bert-VITS2-2.7.0
│  └─ voice-venv\py310-cu128
├─ data
│  ├─ conversations\shion_chat.db
│  └─ voice\models.json
├─ artifacts
│  ├─ voice
│  ├─ images
│  ├─ attachments
│  └─ exports
├─ cache\huggingface
├─ temp
├─ logs
├─ image_output\experimental   # 過去の画像実験出力
└─ training_output
```

`StoragePaths` のdefault rootは `D:\AI\Project_SHION` です。`SHION_DATA_ROOT` はabsolute pathだけを受け付けます。

## 12. Backup対象

### 必ずバックアップを推奨

| 対象 | 理由 |
|---|---|
| `data\conversations\shion_chat.db` | Conversation Historyのcanonical store |
| `data\voice\models.json` | Voice registry、review/test/enable状態 |
| `models\voice\commercial\ShizukaLab_Nene_VoicePalette_V3_0` | 購入済み有償モデル |
| `models\voice\_incoming\ShizukaLab_Nene_VoicePalette_V3_0.zip` | 購入原本 |
| `artifacts\voice` | 再生履歴に紐づく生成WAV。必要なら保存 |

DBはChatを正常停止してからコピーするのが最も単純で安全です。稼働中にfile copyする場合、SQLite WAL/SHMを取りこぼさないようオンラインbackup APIを使う別手順が必要です。

Neneモデル、ZIP、LICENSE、READMEは有償かつ再配布禁止です。Git push、public cloud共有、第三者への提供は禁止です。暗号化されたOwner private backupへ限定してください。

### 再生成・再取得可能

| 対象 | 扱い |
|---|---|
| `cache\huggingface` | 再取得可能。通常backup不要 |
| `temp` | 一時データ。通常backup不要 |
| Python `__pycache__` / pytest cache | 再生成可能 |
| Hugging Face由来model | revision/license/取得可否を確認できるなら再取得可能。ただし時間節約のためprivate backupは任意 |
| Voice artifacts | TTSを再実行可能だが、exact artifact identityを残したい場合はbackup対象 |

## 13. Quick Reference

### Quick Start

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
$env:SHION_DATA_ROOT = 'D:\AI\Project_SHION'
training\.venv\Scripts\python.exe app\server.py --model ministral3_official
```

開く:

```text
http://127.0.0.1:8765/
```

待つ表示:

```text
Conversation Ready / History PERSISTENT / Voice AVAILABLE
```

### Quick Stop

Chatを起動したPowerShellで:

```text
Ctrl+C
```

Voice Consoleを別PowerShellで手動起動していた場合は、そのPowerShellでも `Ctrl+C` を押します。

## 検証記録

2026-08-13に確認した項目:

- Chat startup with `training\.venv\Scripts\python.exe app\server.py --model ministral3_official`: **PASS**
- Conversation state `Ready`: **PASS**
- Persistent History `PERSISTENT`: **PASS**
- Voice lazy startup: **PASS**
- Voice registry schema 1 / 7 models / Nene 2 IDs: **PASS**
- Owner-approved `SHION Default` preset / Nene V3 / Bright: **PASS**
- Nene V3 / Neutral Read Aloud: `GENERATING -> READY`: **PASS**
- Browser WAV load and playback progress: **PASS**
- Voice Artifact persistence: **PASS**
- Local bind 127.0.0.1:8765 and 127.0.0.1:8766: **PASS**
- Chat shutdown signal followed by 8765/8766 listener closure: **PASS**
- Tailscale Serve HTTPS route and PC TLS handshake: **PASS**
- Latest iPhone Safari access: **UNVERIFIED**（iPhone offline）
- Stable Diffusion startup: **UNAVAILABLE / UNVERIFIED**（backend/venv/entry pointなし）

## Owner launcher / Desktop shortcut

Repository rootの `Start-SHION.ps1` は、exact root、absolute data root、8765 collision、Heretic default、Ready待ちを検証してWorkspaceを開きます。Voiceはlazyのままで、Stable Diffusionは起動しません。

```powershell
Set-Location 'C:\Users\PC\Documents\ChatGPT\Project_SHION\official-main'
.\Start-SHION.ps1
```

Desktop shortcutはOwnerが次を一度実行して作成します。Desktop pathはWindows Special Folder APIから解決し、hardcodeしません。

```powershell
.\Install-SHION-DesktopShortcut.ps1
```

`Stop-SHION.ps1` は未実装です。現在のvenv launcher / child Python構成に対して外部から保証されたgraceful shutdown契約がなく、PID killではDB/Voice/model lifecycleを安全に完了できないためです。通常停止は起動consoleで `Ctrl+C` を使います。

実装済みのStart側:

- exact repository/data root検証
- 8765の既存SHION再利用／不明listener拒否
- allowlisted Heretic alias
- Chat起動とReady待ち
- Browser open
- Voice lazy startup
- Stable Diffusion非起動
- processの無差別停止なし
