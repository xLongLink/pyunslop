# Agent workflow

DO run `uvx pyunslop` and fix any warnings

## Commit Message Structure

DO use this structure for commit messages:

<commit-message>
	<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert</type>
	<scope>api|sdk|web (optional)</scope>
	<description>A short, imperative summary of the change</description>
</commit-message>

## Merge Request Structure

DO use this structure for merge requests:

<merge-request>
	<title>Use the commit message structure</title>
	<summary>What changed and why</summary>
	<validation>Checks run and results, or why not run</validation>
	<labels>Change-type labels from .github/release.yml and applicable area labels: api|sdk|web</labels>
</merge-request>
