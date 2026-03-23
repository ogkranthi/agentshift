Output docs/demo.gif

Set FontSize 14
Set Width 900
Set Height 400
Set Theme "Dracula"

# Copy the weather skill and convert it
Type "cp -r ~/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather ./weather-skill"
Sleep 500ms
Enter
Sleep 1s

Type "agentshift convert ./weather-skill --from openclaw --to claude-code --output ./weather-claude"
Sleep 500ms
Enter
Sleep 2s

# Show the generated CLAUDE.md
Type "cat ./weather-claude/CLAUDE.md"
Sleep 500ms
Enter
Sleep 2s

# Show the generated settings.json
Type "cat ./weather-claude/settings.json"
Sleep 500ms
Enter
Sleep 2s
