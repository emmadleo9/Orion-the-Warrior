import * as path from 'path';

/**
 * Resolve a plugin's `main` entry to an absolute path, asserting it stays inside
 * <pluginsDir>/<pluginId>. `main` comes from a user-supplied manifest, so a
 * value like '../../etc/passwd' (or an absolute path) must be rejected BEFORE require().
 */
export function resolvePluginMainPath(pluginsDir: string, pluginId: string, main: string): string {
  const base = path.resolve(pluginsDir, pluginId);
  const mainPath = path.resolve(base, main);
  if (mainPath !== base && !mainPath.startsWith(base + path.sep)) {
    throw new Error(`Plugin ${pluginId} main path escapes the plugin directory`);
  }
  return mainPath;
}

/**
 * The same containment guard, anchored to a plugin's own package directory rather than to the
 * configured plugins root. Callers that hold a loaded plugin's `packageDir` use this: the package
 * may sit in the legacy directory, in which case resolving against `plugins.dir` names a file that
 * does not exist.
 */
export function resolvePluginEntryPath(packageDir: string, entry: string): string {
  return resolvePluginMainPath(path.dirname(packageDir), path.basename(packageDir), entry);
}

/**
 * Sibling directory names an in-place plugin update stages into / backs up to (see
 * PluginsService.updatePackageInner). Dot-prefixed so the boot directory scan skips them, and placed
 * inside the plugins dir so the swap renames stay on one filesystem (EXDEV-safe). The scanner's
 * boot-time reconciler (recoverInterruptedUpdates) keys off these exact names.
 */
export function pluginUpdateStagingDirName(pluginId: string): string {
  return `.${pluginId}.new`;
}
export function pluginUpdateBackupDirName(pluginId: string): string {
  return `.${pluginId}.bak`;
}
