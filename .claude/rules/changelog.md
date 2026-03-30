---
paths:
  - "CHANGELOG.md"
---

# Changelog Maintenance

**Format**: [Keep a Changelog](https://keepachangelog.com/) with [Semantic Versioning](https://semver.org/).

**Every PR** must include an entry under `## [Unreleased]`.

## Version Bump Rules

- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
- **MINOR** (x.Y.0): New features, backward-compatible additions
- **PATCH** (x.y.Z): Bug fixes, minor improvements

## Entry Format

```markdown
## [Unreleased]

### Added
- **Feature Name** - Brief description of what was added
  - Implementation detail if needed

### Fixed
- **Bug Name** - What was broken and how it was fixed
```

Categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

## Best Practices

- Write from the user's perspective
- Include enough detail to understand the change without reading code
- Reference issue/PR numbers when relevant: `(#123)`
- Group related changes under descriptive subheadings
- For significant changes, add a `### Technical Details` section listing affected files and migrations
