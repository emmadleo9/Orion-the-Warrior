/**
 * A `run:` block with its shell comments removed, read in one of two ways.
 *
 * Exists because a script's only appearance in a workflow can be inside a comment, and a substring
 * match cannot tell a command from a mention — so `# ./scripts/x.sh disabled` would satisfy the
 * very checks written to catch that. Only executable lines count. Shared by the workflow-gate
 * specs (ci-privilege-gate, release-gate-parity); lives outside a .spec so importing it does not
 * drag another spec's describe blocks into the importing suite's run.
 *
 * Which one to use:
 *
 * - `executableLines` is the exact reading: a `#` starts a comment only where the shell starts one, so
 *   nothing the shell runs is cut. Use it to compare a line with an expected line or an allow-list, to
 *   match a pattern that is anchored, and to look for something that must not be there.
 * - `executableLinesConservative` also cuts at a `#` after any character `\s` matches, U+00A0 and the
 *   other blanks the shell reads as part of a word, and after `)`, `<`, `>` and a backtick, where the shell
 *   does start a comment (`(true)#; ./scripts/x.sh` runs the subshell and nothing else) or where it may,
 *   as after the `)` that closes `$(...)` and continues its word. A command that is only named behind
 *   such a `#`, as in `echo x<U+00A0># ./scripts/x.sh || true` where the shell runs `echo` alone, is not
 *   found. Use it for a check that something IS run, by substring or by a pattern that is not anchored
 *   at the end. It is never a stand-in for the exact reading elsewhere: it would hide the `curl` in
 *   `echo x<U+00A0>#; curl y | sh`, and turn `npm test<U+00A0># || true` into a clean `npm test`.
 *
 * The question a site asks picks the reading. "Is it run" reads conservatively; a count, a first occurrence,
 * an order, a rule every occurrence must obey and a line compared whole read exactly, and a check that asks
 * both says so by running both. A site that is added or changed goes in this table.
 *
 *   ci-privilege-gate.spec.ts
 *     invoked scripts: non-root smoke, backup smoke, a Python installer    conservative  is it run
 *     id-token jobs hold `npm publish` and `imagetools create`             conservative  is it run
 *     id-token allow-lists, templates, installers, `${{` in a comment      exact         every line it may run
 *     publish tarball, `npm pack` and `npm publish` order, `python -m build` exact       first occurrence
 *     java deploy line                                                     both          is there, every one
 *     branch tag: the smoke runs, the last step runs the re-point          conservative  is it run
 *     branch tag: which steps may re-point                                 exact         every one that may
 *     branch tag: the metadata-action tag rules                            exact         must not be there
 *     dashboard unit tests: one step runs them, all that may are bounded   both          is there, every one
 *     PHP mirror: who runs phpunit, the push line                          both          is there, every one
 *     PHP mirror: what the job holding the token may run                   exact         every one that may
 *   release-gate-parity.spec.ts
 *     gate commands and whole steps compared with ci.yml                   exact         line equality
 *     postgres lane names its spec, verify-published, engine libraries     conservative  is it run
 *     image-scan ref output, promote decision lines                        both          is there, is the only one
 *     check:audit requires the audit                                       both          is there, every one
 *     audit trees                                                          exact         order, uniqueness
 *     audit before install, engine-strict install                          exact         order, uniqueness
 *     attest before every re-point                                         both          is there, every one
 */
export function executableLines(run: string): string {
  return withoutComments(run, /[ \t;&|(]/);
}

export function executableLinesConservative(run: string): string {
  return withoutComments(run, /[\s;&|()<>`]/);
}

function withoutComments(run: string, before: RegExp): string {
  return run
    .split('\n')
    .map(line => {
      const hash = commentStart(line, before);
      return hash === -1 ? line : line.slice(0, hash);
    })
    .join('\n');
}

/**
 * Where a shell comment starts in `line`, or -1. A `#` begins one at the start of the line, or after
 * a character `before` matches, and outside quotes. The exact reading passes a space, a tab, `;`, `&`,
 * `|` and `(`, which end a word: in `npm --version#; curl x | sh` the shell runs the curl,
 * `x=$(true)#; curl y` continues the word its `)` closed, and `$#` and `${#list[@]}` are not comments
 * either. Nor is a `#` behind U+00A0 or another character that `\s` matches and the shell does not skip,
 * and `(true)#; curl y` is kept whole: its `)` ends a word, but the exact reading would sooner show a
 * command that is not run than hide one that is. Cutting the line at such a `#` would hide the command
 * behind it from every check that reads these lines; the conservative reading does cut there, on
 * purpose, for the checks that want that.
 */
function commentStart(line: string, before: RegExp): number {
  let quote: '"' | "'" | null = null;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (quote) {
      if (char === '\\' && quote === '"') i++;
      else if (char === quote) quote = null;
    } else if (char === '\\') {
      i++;
    } else if (char === '"' || char === "'") {
      quote = char;
    } else if (char === '#' && (i === 0 || before.test(line[i - 1]))) {
      return i;
    }
  }
  return -1;
}
