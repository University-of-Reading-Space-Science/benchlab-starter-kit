#!/usr/bin/env bash
# Final upload: check the kit, zip it, fetch your upload form from the
# portal, and upload it.
#
#   bash submit_final.sh           # check, zip, upload
#   bash submit_final.sh status    # show your status and build log links
#
# Needs a .team file next to this script. Create it with:
#   cp .team.example .team     (then put your portal link in it)
#
# Needs: bash, curl, jq, zip.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

die() { echo "ERROR: $*" >&2; exit 1; }

for tool in curl jq zip; do
  command -v "$tool" >/dev/null 2>&1 || die "'$tool' is not installed"
done

[ -f .team ] || die ".team not found. Run: cp .team.example .team   and put your portal link in it."
source ./.team
case "${PORTAL:-}" in
  http*) ;;
  *) die "PORTAL in .team is empty or is not a link. Paste the full link from your email, inside the quotes." ;;
esac

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fetch_portal() {
  curl -fsS "$PORTAL" > "$TMP/portal.json" \
    || die "could not get your page from the portal. A 403 means the PORTAL link in .team is wrong or cut off."
  jq -e . "$TMP/portal.json" >/dev/null 2>&1 || die "the portal did not return JSON."
}

show_status() {
  jq '{submission_id, eligibility, conformance, conformance_at, failure_reason}' "$TMP/portal.json"
  echo "Build log links (valid for 1 hour, open with curl or a browser):"
  jq -r '.logs[]?.url' "$TMP/portal.json"
}

submit() {

  echo "1/3 Zipping..."
  rm -f kit.zip
  (cd submission_pack && zip -qr ../kit.zip . -x '*.DS_Store')

  echo "2/3 Getting your upload form from the portal..."
  fetch_portal
  URL=$(jq -r '.upload.url // empty' "$TMP/portal.json")
  [ -n "$URL" ] || die "the portal did not return an upload form."
  ARGS=()
  while IFS=$'\t' read -r k v; do
    ARGS+=(--form-string "$k=$v")
  done < <(jq -r '.upload.fields | to_entries[] | [.key, .value] | @tsv' "$TMP/portal.json")
  [ "${#ARGS[@]}" -gt 0 ] || die "the upload form had no fields."

  echo "3/4 Uploading kit.zip..."
  # 'file' must be the last form field: S3 ignores anything after it.
  CODE=$(curl -sS -o "$TMP/resp.txt" -w '%{http_code}' "${ARGS[@]}" -F 'file=@kit.zip' "$URL") \
    || die "the upload request failed (network problem?)."

  if [ "$CODE" = "204" ]; then
    echo "HTTP status: 204. Your zip arrived."
    echo "The build takes a few minutes. Then run:  bash submit_final.sh status"
  else
    echo "HTTP status: $CODE. The upload was rejected:" >&2
    cat "$TMP/resp.txt" >&2
    echo >&2
    die "your upload form lasts 1 hour, so just run this script again."
  fi
}

case "${1:-submit}" in
  submit) submit ;;
  status) fetch_portal; show_status ;;
  *) die "usage: bash submit_final.sh [status]" ;;
esac
