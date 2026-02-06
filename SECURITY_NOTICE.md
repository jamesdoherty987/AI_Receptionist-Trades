# 🚨 SECURITY NOTICE - IMMEDIATE ACTION REQUIRED

## Critical: Exposed Credentials Detected

Your repository contains **LIVE API KEYS AND CREDENTIALS** that have been committed to git history. Even though these files are now in `.gitignore`, they remain in your git history and may be publicly accessible if pushed to GitHub.

## Files Containing Exposed Secrets

1. **`.env`** - Contains:
   - Stripe Live Secret Key
   - Twilio Account SID & Auth Token
   - OpenAI API Key
   - ElevenLabs API Key
   - Deepgram API Key

2. **`config/credentials.json`** - Contains:
   - Google OAuth Client Secret

3. **`config/token.json`** - Contains:
   - Google OAuth Refresh Token

4. **`ngrok.yml`** - Contains:
   - Ngrok Auth Token

## Required Actions

### 1. Immediately Rotate All API Keys

Visit each service and generate new keys:

- **Stripe**: https://dashboard.stripe.com/apikeys
- **Twilio**: https://console.twilio.com/
- **OpenAI**: https://platform.openai.com/api-keys
- **ElevenLabs**: https://elevenlabs.io/app/settings/api-keys
- **Deepgram**: https://console.deepgram.com/
- **Google OAuth**: https://console.cloud.google.com/apis/credentials
- **Ngrok**: https://dashboard.ngrok.com/get-started/your-authtoken

### 2. Remove Sensitive Files from Git History

If you haven't pushed to a remote repository yet:
```bash
# Remove files from git tracking (keeps local files)
git rm --cached .env
git rm --cached config/credentials.json
git rm --cached config/token.json
git rm --cached ngrok.yml
git rm --cached .vscode -r
git rm --cached .python-version
git rm --cached frontend/.vscode -r

# Commit the removal
git commit -m "Remove sensitive files from git tracking"
```

If you HAVE pushed to GitHub/remote:
```bash
# You need to use git filter-repo or BFG Repo-Cleaner
# See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
```

### 3. Update .env with New Keys

After rotating, update your local `.env` file with new credentials.

### 4. Verify .gitignore

Your `.gitignore` is properly configured. Verify no sensitive files are tracked:
```bash
git status
```

## Best Practices Going Forward

1. ✅ **Never commit** `.env`, `config/credentials.json`, `config/token.json`, or files with secrets
2. ✅ **Always use** `.env.example` as a template (without real values)
3. ✅ **Check before committing**: Run `git status` and review changed files
4. ✅ **Use environment variables** for all secrets in production (Render/Vercel)
5. ✅ **Regularly rotate** API keys as a security practice

## Additional Security Recommendations

- Enable 2FA on all service accounts
- Use least-privilege access for API keys
- Monitor API usage for anomalies
- Consider using secret management tools (AWS Secrets Manager, HashiCorp Vault, etc.)

---

**IMPORTANT**: Do not delete this file until you have completed all actions above.
