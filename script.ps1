# Replace with your actual bot token and public URL
$botToken = "7566372642:AAF39GqkMbuYy5vFpv6yizmp_RkfC9NKZHU"
$webhookUrl = "https://easy-seals-battle.loca.lt/webhook"

$body = "url=$($webhookurl)"
# Make the POST request to set the webhook
Invoke-RestMethod -Uri "https://api.telegram.org/bot$botToken/setWebhook" `
  -Method Post `
  -Body $body `
  -ContentType "application/x-www-form-urlencoded"

