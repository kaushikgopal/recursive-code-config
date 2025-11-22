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

# === Package Targets ===

package: build ## Package fonts and create GitHub release for homebrew
	@echo "📦 Starting package process..."
	@$(eval VERSION := $(shell grep "Family Name:" premade-configs/config.kg.yaml | sed 's/.*KG \([0-9]*\).*/\1/'))
	@$(eval FONT_VERSION := $(shell grep "Base Recursive Version:" premade-configs/config.kg.yaml | sed 's/.*"\([0-9.]*\)".*/\1/'))
	@echo "📋 Version: $(VERSION), Font Version: $(FONT_VERSION)"
	@echo "🗜️  Creating zip file..."
	@cd fonts && zip -r -X ../recursive-$(VERSION).$(FONT_VERSION).zip RecursiveKG$(VERSION)/
	@echo "🔐 Calculating SHA256..."
	@$(eval SHA := $(shell shasum -a 256 recursive-$(VERSION).$(FONT_VERSION).zip | awk '{print $$1}'))
	@echo "$(SHA)" | pbcopy
	@echo "   SHA256: $(SHA) (copied to clipboard)"
	@echo "📤 Committing and pushing changes to recursive-code-config..."
	@git add -A
	@git commit -m "recursive kg $(VERSION)" || true
	@git push origin main || git push origin master
	@echo "🚀 Creating GitHub release..."
	@gh release create v$(VERSION) \
		--repo kaushikgopal/recursive-code-config \
		--title "Recursive KG $(VERSION)" \
		--notes "Recursive KG $(VERSION) - Font version $(FONT_VERSION)" \
		recursive-$(VERSION).$(FONT_VERSION).zip
	@echo "🍺 Updating homebrew formula..."
	@if [ ! -d "../homebrew-tools" ]; then \
		echo "   Cloning homebrew-tools repository..."; \
		cd .. && git clone https://github.com/kaushikgopal/homebrew-tools.git; \
	fi
	@cd ../homebrew-tools && git pull origin main || git pull origin master
	@echo "   Updating version, sha256, and url..."
	@sed -i '' 's/version ".*"/version "$(VERSION).$(FONT_VERSION)"/' ../homebrew-tools/Casks/font-recursive-kg.rb
	@sed -i '' 's/sha256 ".*"/sha256 "$(SHA)"/' ../homebrew-tools/Casks/font-recursive-kg.rb
	@sed -i '' 's|url ".*"|url "https://github.com/kaushikgopal/recursive-code-config/releases/download/v$(VERSION)/recursive-$(VERSION).$(FONT_VERSION).zip"|' ../homebrew-tools/Casks/font-recursive-kg.rb
	@echo "   Updating font paths..."
	@sed -i '' 's|font "[^/]*/RecursiveKG[0-9]*-\([^-]*\)-[0-9.]*\.ttf"|font "RecursiveKG$(VERSION)/RecursiveKG$(VERSION)-\1-$(FONT_VERSION).ttf"|g' ../homebrew-tools/Casks/font-recursive-kg.rb
	@echo "   Committing and pushing homebrew-tools..."
	@cd ../homebrew-tools && git add Casks/font-recursive-kg.rb
	@cd ../homebrew-tools && git commit -m "update: recursive kg $(VERSION)"
	@cd ../homebrew-tools && git push origin main || git push origin master
	@echo "✅ Package complete! Release v$(VERSION) created and homebrew formula updated."
	@echo "   Release URL: https://github.com/kaushikgopal/recursive-code-config/releases/tag/v$(VERSION)"
