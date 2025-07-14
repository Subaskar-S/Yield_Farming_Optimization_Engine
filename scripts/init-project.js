const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

/**
 * Project initialization script for AI-Driven Yield Farming Optimization Engine
 * This script sets up the development environment and installs dependencies
 */

console.log('🚀 Initializing AI-Driven Yield Farming Optimization Engine...\n');

// Check if Node.js version is compatible
const nodeVersion = process.version;
const requiredVersion = 'v16.0.0';
if (nodeVersion < requiredVersion) {
    console.error(`❌ Node.js ${requiredVersion} or higher is required. Current version: ${nodeVersion}`);
    process.exit(1);
}

// Check if Python is installed
try {
    const pythonVersion = execSync('python --version', { encoding: 'utf8' });
    console.log(`✅ Python detected: ${pythonVersion.trim()}`);
} catch (error) {
    console.error('❌ Python is not installed or not in PATH');
    process.exit(1);
}

// Function to run command with error handling
function runCommand(command, description) {
    console.log(`📦 ${description}...`);
    try {
        execSync(command, { stdio: 'inherit' });
        console.log(`✅ ${description} completed\n`);
    } catch (error) {
        console.error(`❌ ${description} failed:`, error.message);
        process.exit(1);
    }
}

// Function to create file if it doesn't exist
function createFileIfNotExists(filePath, content) {
    if (!fs.existsSync(filePath)) {
        fs.writeFileSync(filePath, content);
        console.log(`✅ Created ${filePath}`);
    } else {
        console.log(`⚠️  ${filePath} already exists, skipping...`);
    }
}

// Install Node.js dependencies
runCommand('npm install', 'Installing Node.js dependencies');

// Install Python dependencies
runCommand('pip install -r requirements.txt', 'Installing Python dependencies');

// Create .env file from example if it doesn't exist
if (!fs.existsSync('.env')) {
    fs.copyFileSync('.env.example', '.env');
    console.log('✅ Created .env file from .env.example');
    console.log('⚠️  Please update .env file with your configuration');
} else {
    console.log('⚠️  .env file already exists, skipping...');
}

// Create essential placeholder files
const placeholderFiles = [
    {
        path: 'contracts/interfaces/IERC20.sol',
        content: `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}
`
    },
    {
        path: 'ml/__init__.py',
        content: '# AI/ML module for yield farming optimization\n'
    },
    {
        path: 'backend/__init__.py',
        content: '# Backend services module\n'
    },
    {
        path: 'keepers/__init__.py',
        content: '# Automation and keeper services\n'
    },
    {
        path: 'tests/__init__.py',
        content: '# Test suite\n'
    }
];

placeholderFiles.forEach(file => {
    const dir = path.dirname(file.path);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
    createFileIfNotExists(file.path, file.content);
});

// Compile smart contracts
console.log('🔨 Compiling smart contracts...');
try {
    execSync('npx hardhat compile', { stdio: 'inherit' });
    console.log('✅ Smart contracts compiled successfully\n');
} catch (error) {
    console.log('⚠️  No contracts to compile yet, this is normal for initial setup\n');
}

// Create database directory for local development
const dbDir = 'backend/database/migrations';
if (!fs.existsSync(dbDir)) {
    fs.mkdirSync(dbDir, { recursive: true });
    console.log(`✅ Created ${dbDir}`);
}

// Create logs directory
const logsDir = 'logs';
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir);
    console.log(`✅ Created ${logsDir}`);
}

console.log('🎉 Project initialization completed successfully!\n');

console.log('📋 Next steps:');
console.log('1. Update .env file with your configuration');
console.log('2. Start local blockchain: npm run node');
console.log('3. Deploy contracts: npm run deploy:local');
console.log('4. Start backend API: npm run backend:dev');
console.log('5. Start frontend: npm run frontend:dev');
console.log('6. Train ML models: npm run ml:train');
console.log('\n📚 Documentation:');
console.log('- Architecture: docs/ARCHITECTURE.md');
console.log('- API docs: docs/api/');
console.log('- User guides: docs/guides/');

console.log('\n🔧 Development commands:');
console.log('- npm test: Run all tests');
console.log('- npm run compile: Compile smart contracts');
console.log('- npm run simulation: Run yield farming simulation');
console.log('- npm run analysis: Run yield analysis');

console.log('\n⚠️  Important:');
console.log('- Never commit .env file to version control');
console.log('- Use testnet for development and testing');
console.log('- Review security documentation before mainnet deployment');
