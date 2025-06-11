#!/bin/bash

set -e

echo "🔧 Initializing project..."
npm init -y

echo "📦 Installing dependencies..."
npm install --save-dev \
  playwright \
  @cucumber/cucumber \
  ts-node \
  typescript \
  @types/node

echo "🌐 Installing Playwright browsers..."
npx playwright install --with-deps

echo "📁 Creating base folder structure..."
mkdir -p features step-definitions support

echo "📝 Creating tsconfig.json..."
cat <<EOF > tsconfig.json
{
  "compilerOptions": {
    "target": "ES6",
    "module": "CommonJS",
    "lib": ["ES6", "DOM"],
    "outDir": "./dist",
    "rootDir": "./",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["**/*.ts"]
}
EOF

echo "📜 Adding NPM test script..."
npx npm set-script test:e2e "cucumber-js --require-module ts-node/register --require ./step-definitions/**/*.ts features"

echo "✅ Done! Now you can run tests with:"
echo "    npm run test:e2e"
