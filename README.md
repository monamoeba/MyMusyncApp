# MyMusync

A Django web app that transfers a playlist from **YouTube** to **Spotify** — sign in to both, pick a playlist, and it recreates it on Spotify by matching each video to a track.

I built this as a teenager, before the AI era (only scouring StackOverflow and API docs). It's kept here as-is in terms of design and logic but I've since gone back and cleaned up the security and packaging issues that came from not knowing better at the time (see [What I'd do differently now](#what-id-do-differently-now)).

<details>
<summary>📹 Demo walkthrough</summary>

A raw, unedited screen recording originally made to demonstrate every success/failure path for a course assessment so not the best demo vid but it shows the full OAuth → transfer flow end to end. 
(Also the UI is absolutely awful T_T)

[Watch on YouTube](https://youtu.be/MfmZbekP9O0)

</details>

## How it works

1. **Authorise with YouTube** (Google OAuth2) and pick one of your playlists.
2. The app pulls every video in that playlist via the **YouTube Data API**.
3. For each video, it uses `yt-dlp` to resolve the underlying track/artist metadata. Where that's missing (a lot of music videos on YouTube don't tag it), a hand-written parser (`ytAPI/YTAPI.py: superSongParser`) falls back to pattern-matching the video title itself — stripping suffixes like "(Official Music Video)" / "(Official Audio)" / "(Lyrics)" and splitting on separators like `-`, `—`, `by`, and quotation marks to guess the artist and song title.
4. **Authorise with Spotify** and create a new playlist there.
5. Each resolved track is searched for on Spotify and added to the new playlist. Anything that couldn't be confidently matched is reported back at the end instead of silently dropped.

## Features

- Full OAuth2 flows against two real, independent third-party APIs (Google/YouTube and Spotify), including token refresh handling
- A custom fallback parser for messy YouTube video titles instead of relying purely on official metadata
- Paginates through YouTube API responses to handle playlists larger than one page (50 items)
- Reports which songs couldn't be transferred, rather than failing the whole operation

## Tech stack

- **Backend:** Django
- **APIs:** YouTube Data API v3 (`google-api-python-client`, `google-auth-oauthlib`), Spotify Web API (`spotipy`)
- **Metadata extraction:** `yt-dlp`
- **Frontend:** Django templates + Bootstrap

## Setup

```
pip install -r requirements.txt
cp .env.example .env      # fill in a Django secret key + Google/Spotify OAuth credentials
python manage.py migrate
python manage.py runserver
```

Requires a Google Cloud OAuth client (Web application, YouTube Data API v3 enabled) and a Spotify app, each with their redirect URI set to `http://127.0.0.1:8000/...` — see `.env.example` for the exact variables and URIs.

## What I'd do differently now

Being upfront about the rough edges rather than hiding them:

- **The playlist transfer is fully synchronous** — it blocks the request while it calls `yt-dlp` and the Spotify API once per song. For a large playlist that's slow and could easily hit a request timeout. There's a half-finished `celery-progress` integration in an earlier version of this project that was never wired up to an actual background task; doing this properly (Celery + a progress bar) would be the first thing I'd add.
- **No automated tests.** The parsing logic in `superSongParser` in particular would benefit a lot from a table of title → (artist, song) test cases.
- **No handling for the YouTube Data API's daily quota**, which is easy to hit during testing since fetching playlists/videos costs quota units per call.
- Originally, both API secrets were hardcoded/committed directly to source control and the app's redirect URLs were hardcoded to a fixed host — both fixed in the current version.

## License

MIT — see [LICENSE](LICENSE).
