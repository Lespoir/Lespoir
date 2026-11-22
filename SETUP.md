# Maintaining this profile

`README.md` is the public profile. Edit its introduction and article links by hand.
The daily workflow updates the marked chart section in `README.md` and the generated files in `assets/`. Text outside the `PR-CHART` markers is preserved.

## Enable the daily refresh

1. Create a [classic personal access token](https://github.com/settings/tokens/new?description=Profile%20PR%20counts&scopes=repo) in your own GitHub account, with an expiration and the `repo` scope. This supports private repositories across multiple owners. That scope grants broader repository access than the script uses; the script only searches for counts. Authorize SSO for any organization that requires it. Organization policy can restrict access.
2. Add it as an **Actions repository secret** named `PR_STATS_TOKEN` in [this repository's secret settings](https://github.com/Lespoir/Lespoir/settings/secrets/actions/new). Enter the token directly in GitHub, not in a chat or a file.
3. Open [Update merged PR chart](https://github.com/Lespoir/Lespoir/actions/workflows/update-pr-chart.yml) and choose **Run workflow**, or ask the assistant to run it after the secret is saved.

The normal schedule is 06:23 Bogotá every day. GitHub can delay scheduled runs.
An expired, missing or invalid token fails the run and leaves the last committed chart visible.
The displayed update time makes an old snapshot recognizable.

A fine-grained token is an alternative if you choose a single repository owner and grant the required read access to its pull requests. Its results are limited to repositories that token can access. Fine-grained tokens cannot span multiple organizations. Changing token access can change the totals even when no PRs changed.

The workflow uses the built-in `GITHUB_TOKEN` to commit the public images and publish the interactive page through GitHub Pages. It uses `PR_STATS_TOKEN` only during the count lookup. It does not run on pull requests or fork contributions.

## What the chart counts

- Pull requests **authored by Lespoir** that were merged, regardless of who merged them.
- The most recent **365 calendar days**, including today.
- Each PR belongs to its **merge date in America/Bogota** (UTC−05:00).
- All public and private repositories visible to the supplied token.
- All branches and repository owners; no repository names or PR details appear in output.

The script requests GitHub's aggregate `issueCount` for each day, rather than fetching PR records. This avoids the search API's 1,000-record pagination limit. It makes 27 requests containing up to 14 daily searches each, with a short pause between requests. GitHub's search index can lag recent merges.

The README shows a full-width image with no click action. Its monthly bars have exact counts, an exact total for the displayed period, the date range and the last update time. The profile displays August 1, 2026 onward, restricted to dates present in the rolling 365-day source snapshot. Its total includes only those displayed dates. Months are calendar months; asterisks identify partial months, and the final month is purple. Zero months remain visible. The vertical axis starts at zero and adjusts to the largest monthly count.

The earlier [daily-detail page](https://lespoir.github.io/Lespoir/) remains available at its existing address, but the profile no longer links to it. Both views use the same daily JSON snapshot and follow the reader’s light or dark theme. The JSON contains only dates, counts and update metadata. Git history preserves earlier aggregate snapshots.

GitHub's own contribution chart remains below the profile README. This image does not replace or change it.

## Interactive page deployment

In [Pages settings](https://github.com/Lespoir/Lespoir/settings/pages), the source must be **GitHub Actions**. The daily workflow first saves the new counts, then builds and deploys the interactive page from the updated main branch. Changes to page code also deploy automatically on pushes to main. This keeps both views in sync even though commits made by `GITHUB_TOKEN` do not trigger another workflow.

Only the generated `_site/` directory is uploaded to Pages. It contains the standalone chart page, with the same aggregate data already shown in the README. The page has no credentials, API calls or external scripts.

## Run locally

Requires Python 3.9+ with timezone data and the GitHub CLI, already signed in as Lespoir.
No Python packages are required. Do not extract credentials from the CLI.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/update_chart.py
python3 scripts/build_page.py
```

The tests cover Bogotá day boundaries, leap years, counts larger than the search pagination cap, incomplete responses, wrong-account credentials, exact SVG totals, preserving old output after a failed lookup, all 365 day labels in each theme, monthly totals and partial months, zero activity, building daily details from the same JSON snapshot, and preserving hand-written profile content during refresh.

Sources: [GitHub search qualifiers](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests), [token permissions and owner limitations](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens), [scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule).
