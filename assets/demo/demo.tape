# VHS Tape for Agentic-ReadMe-Creator
# Output target: hero GIF under 5MB for GitHub README performance
Output assets/demo/hero-demo.gif
Output assets/demo/hero-demo.mp4

Set FontSize 15
Set Width 900
Set Height 480
Set Padding 20
Set Theme "Catppuccin Mocha"
Set Framerate 30

# Initial pause
Sleep 1s

# Run verified quickstart commands
Type "git clone <repo-url> && cd Agentic-ReadMe-Creator"
Sleep 500ms
Enter
Sleep 2s
Type "pip install -e ."
Sleep 500ms
Enter
Sleep 2s
Type "pytest"
Sleep 500ms
Enter
Sleep 2s
Type "python3 src/agentic_readme/cli.py"
Sleep 500ms
Enter
Sleep 2s

# End on the successful result (peak-end rule)
Sleep 3s
