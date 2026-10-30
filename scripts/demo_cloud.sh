#!/usr/bin/env bash
# Cloud demo: teacher token, absent mark, then parent 403.
# Does not need a working aws login. Type passwords at the prompts.

set -euo pipefail

REGION=eu-north-1
CLIENT=gu8klepolvhrmn91nciogtfcq
API=https://315jy5orj0.execute-api.eu-north-1.amazonaws.com
TEACHER=madalanelenox@gmail.com
PARENT=madalanelenox+parent@gmail.com
TODAY=$(TZ=Africa/Johannesburg date +%F)

token() {
  local user=$1
  local password=$2
  aws cognito-idp initiate-auth \
    --no-sign-request \
    --region "$REGION" \
    --client-id "$CLIENT" \
    --auth-flow USER_PASSWORD_AUTH \
    --auth-parameters USERNAME="$user",PASSWORD="$password" \
    --query 'AuthenticationResult.IdToken' \
    --output text
}

read -s -p "Teacher password for ${TEACHER}: " TEACHER_PW
echo
TEACHER_TOKEN=$(token "$TEACHER" "$TEACHER_PW")
unset TEACHER_PW

echo
echo "== Teacher marks learner 1003 absent for ${TODAY}"
curl -s -w "\nstatus: %{http_code}\n" -X POST \
  -H "Authorization: ${TEACHER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"student_id\":1003,\"class_id\":10,\"attendance_date\":\"${TODAY}\",\"status\":\"absent\"}" \
  "${API}/attendance"

echo
echo "== Teacher reads today for learner 1003"
curl -s -w "\nstatus: %{http_code}\n" \
  -H "Authorization: ${TEACHER_TOKEN}" \
  "${API}/attendance/today?student_id=1003&attendance_date=${TODAY}"

read -s -p "Parent password for ${PARENT}: " PARENT_PW
echo
PARENT_TOKEN=$(token "$PARENT" "$PARENT_PW")
unset PARENT_PW

echo
echo "== Parent POST /attendance should be 403"
curl -s -w "\nstatus: %{http_code}\n" -X POST \
  -H "Authorization: ${PARENT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"student_id\":1003,\"class_id\":10,\"attendance_date\":\"${TODAY}\",\"status\":\"present\"}" \
  "${API}/attendance"
