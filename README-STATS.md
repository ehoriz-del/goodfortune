# Good Fortune weekly statistics

Upload `index.html`, `lottery-stats.json`, `scripts/`, and `.github/` to the same GitHub Pages repository.
The workflow runs every Monday at 10:20 UTC and may also be run manually from GitHub Actions.

The updater never substitutes guessed numbers. If a provider changes or blocks its page, the last
verified values remain in place and the Actions log identifies the source needing review. A lottery
without verified statistics has no statistics block at all—there is no unavailable message or empty
space. Korea Lotto 6/45 accepts only the official Donghaeng Lottery statistics page; third-party Korean
lottery statistics are never used. China Super Lotto and the current Lotto Max 7/52 format remain hidden
until a stable, licensable source can be verified. These safeguards prevent stale or incompatible
game-era statistics from being presented as current.
