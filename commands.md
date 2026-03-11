


Here are all available commands:

| Command                         | What it does                                                        |
| ------------------------------- | ------------------------------------------------------------------- |
| `python main.py fetch`          | Fetch jobs from the API, clean, score, and save to `output/jobs.db` |
| `python main.py show`           | Print top results from the database                                 |
| `python main.py search <terms>` | Full-text search across stored listings                             |
| `python main.py stats`          | Show total count, source breakdown, and average score               |
| `python main.py export`         | `output/job_listings.json` — top-scored, for AI eval                |
| `python main.py export-all`     | `output/job_listings_all.json` — everything                         |
| `python main.py export-csv`     | `output/job_listings.csv` — top-scored as CSV                       |
| `python main.py export-all-csv` | `output/job_listings_all.csv` — everything as CSV                   |

**Optional flags:**

```bash
python3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python main.py show   --limit 20 --min-score 0.4
python main.py search python django --limit 10
python main.py export --min-score 0.5 --limit 30
```
