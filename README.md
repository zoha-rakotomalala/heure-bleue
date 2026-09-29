# heure bleue

A gallery wall for a spare screen. One painting at a time, from open museum
collections, chosen to match the colours of whatever you are listening to.

![the wall](docs/wall.png)

- **Paintings** from The Met, the Rijksmuseum and the Musée d'Orsay. 420 public-domain works ship in the index; the indexer can fetch more.
- **Music** from Spotify or Apple Music on macOS, any player on Windows (system media session) and Linux (MPRIS). The album cover's palette picks the painting.
- **A quiet board**: clock, date, weather, sunrise and sunset, a *heure bleue* countdown. Nothing from work.
- **It learns**: keep a painting (♥) and the wall leans toward that artist, museum and century.
- **Themes**: forest, heure bleue, night, charcoal, plum, oxblood, paper, linen, any hex, or a wall that follows the painting.

![themes](docs/themes.png)

Everything runs on your machine, on `127.0.0.1`. No accounts, no API keys, no
telemetry. The only network calls are museum images, Open-Meteo for weather, and
the Spotify cover CDN.

## Install

Python 3.10 or newer.

```sh
git clone https://github.com/zoha-rakotomalala/heure-bleue.git
cd heure-bleue
python3 -m pip install -r requirements.txt
python3 -m heurebleue doctor      # checks Python, Pillow, your player, the index, the port
python3 -m heurebleue start --open
```

Then put the browser window on the spare screen and press `F` for fullscreen.
On macOS, Safari → File → *Add to Dock* gives you a clean web app with no
address bar. Chrome: *Save and share → Install page as app*.

Start at login:

```sh
python3 -m heurebleue service install    # launchd / Task Scheduler / systemd --user
python3 -m heurebleue service remove
```

### Windows

Install the media-session bridge so the wall can see your player:

```sh
py -m pip install winsdk
```

`winsdk` supports Python 3.9–3.12. On 3.13 use the `winrt-*` packages instead
(`pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams`).
Anything that shows in the Windows media overlay works: Spotify, Apple Music,
iTunes, a browser tab.

### Linux

```sh
sudo apt install playerctl      # or dnf / pacman
```

Any MPRIS player works.

## Keys and buttons

Four small buttons sit bottom-right and fade after 4 s of stillness.

| key | action |
|---|---|
| `F` | fullscreen |
| `N`, `space`, `→` | another painting |
| `L` | keep this painting (♥) |
| `K` | open *Kept*, your favorites |
| `T` | wall colour |
| `Esc` | close |

![kept](docs/kept.png)

## Configure

Create `config.json` next to this README. Any key you omit keeps its default.

```json
{
  "port": 8765,
  "theme": "forest",
  "locale": "en-GB",
  "city": { "name": "Amsterdam", "lat": 52.3676, "lon": 4.9041, "timezone": "Europe/Amsterdam" },
  "poll_seconds": 5,
  "min_dwell_seconds": 45,
  "rotate_minutes": 10
}
```

Themes can also be set from the URL: `?theme=night`, `?theme=painting`, `?bg=1f2a1c`.
The choice is remembered per browser.

## The index

`data/paintings.json` holds title, artist, date, museum, image URL and a
five-colour palette for each work. About 500 bytes per painting, no images on
disk. To add more:

```sh
python3 -m heurebleue index --target 800            # all three museums, round-robin
python3 -m heurebleue index --source orsay --target 600
python3 -m heurebleue stories                        # curator texts for Rijksmuseum entries
```

The indexer is deliberately slow (0.8 s between requests, backs off on 429) so it
stays a good citizen of free museum APIs. Photos that include a photographic
calibration strip are detected and skipped. Only public-domain images are kept.

## How the match works

The album cover is reduced to five colours. Each painting in the index already
has five. The distance between two palettes is a weighted nearest-colour sum in
CIELAB, both ways. Favorites shorten the distance for artists, museums and
centuries you keep. The painting changes when the song changes, never sooner
than `min_dwell_seconds` after the last change, so skipping tracks does not make
the wall flicker. When nothing plays, the wall rotates every `rotate_minutes`.

## Data written at runtime

All under `data/`, all git-ignored except the index:

`now_playing.json` (current state) · `favorites.json` · `taste.json` (weights
derived from favorites) · `history.jsonl` (one line per painting shown, with
dwell time and the song) · `cover.jpg` (when the player gives raw artwork).

## Credits

Images and metadata: [The Metropolitan Museum of Art](https://www.metmuseum.org/art/collection) (CC0),
[Rijksmuseum](https://data.rijksmuseum.nl/) (CC0), and Wikimedia Commons uploads of
public-domain works in the [Musée d'Orsay](https://commons.wikimedia.org/wiki/Category:Paintings_in_the_Mus%C3%A9e_d%27Orsay).
Weather: [Open-Meteo](https://open-meteo.com/).

MIT licence.
