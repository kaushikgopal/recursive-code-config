# Default target
default: build

help:		## List all available commands with descriptions
	@awk -F'##' '/^[a-zA-Z0-9_-]+:.*##/ {gsub(/:.*/, ":\t\t", $$1); printf "%s%s\n", $$1, $$2}' $(MAKEFILE_LIST) | \
		awk 'NR%2==1 {print "\033[0m" $$0} NR%2==0 {print "\033[2m" $$0}'
	@echo "\033[0m"

# === Setup Targets ===

setup:	## Set up Python environment and install dependencies
	@echo "🐍 Setting Python version with pyenv..."
	@pyenv local 3.11.8
	@echo "📦 Creating virtual environment..."
	@python -m venv venv
	@echo "📥 Installing dependencies..."
	@venv/bin/pip install -r requirements.txt
	@echo "✅ Setup complete! Virtual environment ready."

# === Build Targets ===

build:	## Build and install Recursive code fonts on Mac
	@echo "❌ removing existing Recursive fonts on Mac..."
	@rm -rf ~/Library/Fonts/"RecursiveKG*"
	@echo "❌ removing existing Recursive fonts in project..."
	@rm -rf fonts/"RecursiveKG*"
	@echo "🔨 Building Recursive fonts..."
	@venv/bin/python scripts/instantiate-code-fonts.py premade-configs/config.kg.yaml font-data/Recursive_VF_1.085.ttf
	@echo "✅ Installing Recursive fonts on Mac..."
	@cp fonts/RecursiveKG*/*.ttf ~/Library/Fonts/
