# Free Code Signing Setup for PRISM Validator

## Quick Setup (5 minutes)

### Step 1: Apply for Free Signing (1 day wait)
1. Go to https://about.signpath.io/product/open-source
2. Fill out the form:
   - **Project URL**: https://github.com/yourusername/psycho-validator
   - **Project Description**: "PRISM - Psychological Research Information Standard for Metadata. A validation tool for psychological research datasets."
   - **License**: (Your license, e.g., MIT)
3. Submit and wait for approval email (usually 1-2 business days)

### Step 2: Add Secrets to GitHub
Once approved, you'll receive:
- Organization ID
- API Token

Add them to your GitHub repository:
1. Go to: `https://github.com/yourusername/psycho-validator/settings/secrets/actions`
2. Click "New repository secret"
3. Add:
   - Name: `SIGNPATH_API_TOKEN`
   - Value: [paste your token]
4. Click "New repository secret" again
5. Add:
   - Name: `SIGNPATH_ORGANIZATION_ID`  
   - Value: [paste your org ID]

### Step 3: Test the Signing
Create a test release:
```bash
git tag -a v1.0.0-test -m "Test release with signing"
git push origin v1.0.0-test
```

Check GitHub Actions:
- Go to Actions tab
- Watch the build process
- The Windows build will automatically sign the executable
- Download the artifact and verify signature

### Step 4: Verify Signature
On Windows:
1. Download `PrismValidator-Windows.zip` from the release
2. Extract and right-click `PrismValidator.exe`
3. Properties → Digital Signatures tab
4. Should show valid signature from SignPath

## Why This Works

### For IT Departments:
- ✅ Digitally signed by trusted Certificate Authority
- ✅ Certificate chain validates to trusted root
- ✅ Verifiable publisher identity
- ✅ Tampering detection
- ✅ Meets most corporate security policies

### For Users:
- ✅ No Windows SmartScreen warnings (after reputation builds)
- ✅ Shows verified publisher in UAC dialogs
- ✅ Antivirus software trusts signed executables more
- ✅ Professional appearance

## Cost: $0
- SignPath is **FREE** for open source projects
- No credit card required
- Unlimited signing operations
- Valid for production use

## Comparison with Paid Options

| Solution | Cost | SmartScreen | IT Acceptance | Setup Time |
|----------|------|-------------|---------------|------------|
| **SignPath (OSS)** | **$0** | ✅ Yes | ✅ Yes | 2 days |
| Paid Certificate | $200-500/year | ✅ Yes | ✅ Yes | Immediate |
| Self-Signed | $0 | ❌ No | ❌ Usually not | Immediate |
| No Signing | $0 | ❌ No | ❌ No | N/A |

## Troubleshooting

### Application was rejected
- Check your repository is public
- Ensure your project has an OSS license
- Repository should have actual code (not empty)

### Signing fails in GitHub Actions
- Check secrets are added correctly (no extra spaces)
- Verify organization ID matches exactly
- Check `.signpath/SignPathConfig.json` exists

### Signature shows but SmartScreen still warns
- Normal for new certificates
- Submit to Microsoft: https://www.microsoft.com/en-us/wdsi/filesubmission
- Reputation builds over ~100-200 downloads over time

## Alternative for Testing Only

If you need to test locally without waiting for SignPath approval:

### Self-Sign (temporary solution):
```powershell
# Create certificate (Run as Administrator)
$cert = New-SelfSignedCertificate -Type Custom -Subject "CN=PRISM Test" -KeyUsage DigitalSignature -CertStoreLocation "Cert:\CurrentUser\My"

# Sign the exe
signtool sign /fd SHA256 /a /t http://timestamp.digicert.com "dist\PrismValidator\PrismValidator.exe"
```

**Note**: Self-signed won't satisfy IT requirements but useful for local testing.

## Next Steps After Setup

1. **Build releases normally**: Just tag and push
2. **Signing happens automatically**: No manual steps needed
3. **Users get signed executables**: Download from GitHub releases
4. **Submit first release to Microsoft**: Help build SmartScreen reputation
5. **Inform IT department**: Provide them with:
   - Download URL
   - Certificate details
   - Signature verification steps

## Support

- **SignPath Support**: support@signpath.io (very responsive)
- **Documentation**: https://about.signpath.io/documentation
- **GitHub Integration**: https://about.signpath.io/documentation/github-actions

Your executable will be properly signed and acceptable to IT departments! 🎉
