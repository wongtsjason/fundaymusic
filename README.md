# 我手寫我歌

香港布廠商會朱石麟中學開放日音樂工作坊小工具。同學一步步選好歌種、樂器、速度、氛圍和語言，寫下 3 至 4 句感謝屋企人的歌詞，然後把 **Style** 和 **Lyrics** 複製到 [Suno](https://suno.com) 的 Custom 模式，生成一首可以帶走的歌。

頁面是靜態的：沒有登入、沒有伺服器、沒有分析、沒有 API 金鑰。歌詞只留在該分頁的瀏覽器裡，用來組成可以複製的文字；關掉分頁就會清掉。

## 在本機打開

用瀏覽器直接打開 `index.html`，或在這個資料夾啟動一個小伺服器：

```bash
python3 -m http.server 8741
```

然後打開 <http://127.0.0.1:8741>。

手機試聽如果沒有聲音，先檢查有沒有開靜音。

## 發佈到 GitHub Pages

網站檔案在倉庫根目錄，適合用 Pages 從根目錄發佈，也適合印成工作紙上的 QR code。

1. 把這個資料夾推上 GitHub。倉庫請設為 **Public**（免費帳戶的 GitHub Pages 需要公開倉庫）。
2. 打開倉庫的 **Settings → Pages**。
3. **Build and deployment** 選 **Deploy from a branch**。
4. Branch 選 `main`，Folder 選 **`/ (root)`**，然後 Save。
5. 等一兩分鐘，網址會是 `https://<帳號>.github.io/<倉庫名>/`。
6. 用這個網址做 QR code，印在工作紙上。同學用電話掃描即可。

已附上空白的 `.nojekyll`，避免 GitHub Pages 的 Jekyll 忽略某些檔案。頁面裡的音訊和樣式都用相對路徑，所以放在個人網站或專案網站的子路徑都可以。

如果學校想改為從 `/docs` 發佈：把 `index.html`、`css/`、`js/`、`audio/`、`favicon.svg` 和 `.nojekyll` 放進 `docs/`，Pages 的 folder 改選 `/docs`。

課堂流程見 [LESSON.md](LESSON.md)。

## 試聽片段

`audio/` 裡六段約 8 秒的 MP3，分別是粵語流行、K-Pop、民謠、抒情、輕快流行、搖滾。

這些是用 `scripts/generate_previews.py` **自行合成**的原創示範，給家長和同學分辨歌種。不是商業歌曲，也沒有使用任何有版權的錄音或取樣。只供這次工作坊課堂使用。

重新生成（需要 Python 3、NumPy、ffmpeg，以及 ffmpeg 的 libmp3lame）：

```bash
python3 scripts/generate_previews.py
```

## 檔案

| 檔案 | 用途 |
| --- | --- |
| `index.html` | 工作坊頁面 |
| `css/styles.css` | 樣式 |
| `js/app.js` | 步驟、試聽、複製 |
| `audio/*.mp3` | 原創歌種示範 |
| `LESSON.md` | 約 40 分鐘課堂流程 |
| `scripts/generate_previews.py` | 重新合成試聽 |
| `favicon.svg` | 小圖示 |

## English

Static, phone-first wizard for the HKWMA Chu Shek Lun Secondary School open-day workshop **我手寫我歌**. Students pick a genre (with an original preview), instruments, tempo, mood, and vocal language, paste 3–4 lines thanking their family, then copy a short English Suno style prompt and their lyrics.

No build step. Open `index.html`, or serve the folder and enable GitHub Pages from the repository root (`main` / `/ (root)`). The clips in `audio/` are original synthesized previews, not commercial recordings.
