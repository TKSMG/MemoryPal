// Adds Google Drive sync to the app.json config when the build has a Google
// sign-in client: the "iOS" OAuth client id from MemoryPal's Google Cloud
// project, in the GOOGLE_IOS_CLIENT_ID environment variable (the repository
// variable of the same name in GitHub Actions). Android needs no id here: its
// OAuth client is matched by package name and signing key.
// Without it the app keeps syncing through the MemoryPal cloud.
module.exports = ({ config }) => {
  const iosClientId = (process.env.GOOGLE_IOS_CLIENT_ID || '').trim();
  if (!iosClientId) return config;
  const reversed = `com.googleusercontent.apps.${iosClientId.replace(/\.apps\.googleusercontent\.com$/, '')}`;
  return {
    ...config,
    plugins: [...(config.plugins || []), ['@react-native-google-signin/google-signin', { iosUrlScheme: reversed }]],
    extra: { ...(config.extra || {}), googleDrive: { iosClientId } },
  };
};
