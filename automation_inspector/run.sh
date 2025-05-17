# automation_inspector/run.sh  (UNIX LF line endings)
#!/usr/bin/env sh
set -e
uvicorn app.main:app --host 0.0.0.0 --port 1234
