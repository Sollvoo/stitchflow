const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') {
    return
  }

  // If a real Apple signing/notarization flow is configured, let electron-builder
  // handle the proper Developer ID signature instead of replacing it with ad hoc.
  const hasAppleSigningSecrets = Boolean(
    process.env.CSC_LINK &&
    process.env.CSC_KEY_PASSWORD &&
    (
      (process.env.APPLE_API_KEY && process.env.APPLE_API_KEY_ID && process.env.APPLE_API_ISSUER) ||
      (process.env.APPLE_ID && process.env.APPLE_APP_SPECIFIC_PASSWORD && process.env.APPLE_TEAM_ID)
    )
  )

  if (hasAppleSigningSecrets) {
    return
  }

  const appName = `${context.packager.appInfo.productFilename}.app`
  const appPath = path.join(context.appOutDir, appName)

  if (!fs.existsSync(appPath)) {
    throw new Error(`App bundle not found for ad hoc signing: ${appPath}`)
  }

  execFileSync('codesign', ['--force', '--deep', '--sign', '-', appPath], {
    stdio: 'inherit',
  })
}
