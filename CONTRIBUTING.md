# Contributing to AI-Driven Yield Farming Platform

Thank you for your interest in contributing to our AI-driven DeFi yield farming platform! This document provides guidelines and information for contributors.

## 🎯 Project Vision

We're building the future of decentralized finance by combining artificial intelligence with yield farming strategies. Our goal is to create a secure, efficient, and user-friendly platform that maximizes returns while managing risk.

## 🤝 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- 🐛 **Bug Reports**: Help us identify and fix issues
- ✨ **Feature Requests**: Suggest new features or improvements
- 💻 **Code Contributions**: Submit bug fixes or new features
- 📚 **Documentation**: Improve guides, API docs, or code comments
- 🧪 **Testing**: Add test cases or improve test coverage
- 🔒 **Security**: Report vulnerabilities or improve security measures

### Getting Started

1. **Fork the Repository**
   ```bash
   git clone https://github.com/Subaskar-S/ai-yield-farming.git
   cd ai-yield-farming
   ```

2. **Set Up Development Environment**
   ```bash
   # Install dependencies
   npm install
   cd backend && pip install -r requirements.txt
   cd ../frontend && npm install
   cd ../ml && pip install -r requirements.txt
   
   # Set up environment variables
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run Tests**
   ```bash
   # Smart contract tests
   npm test
   
   # Backend tests
   cd backend && pytest
   
   # Frontend tests
   cd frontend && npm test
   
   # ML model tests
   cd ml && pytest
   ```

## 🔧 Development Workflow

### Branch Naming Convention

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Critical fixes
- `docs/description` - Documentation updates
- `test/description` - Test improvements

### Commit Message Format

We follow conventional commits for clear and consistent commit messages:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(ml): add LSTM-based yield prediction model
fix(contracts): resolve reentrancy vulnerability in vault withdrawal
docs(api): update authentication endpoint documentation
test(frontend): add unit tests for dashboard components
```

### Pull Request Process

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   npm run test:all
   ```

4. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat(scope): descriptive commit message"
   ```

5. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Use the PR template
   - Provide clear description of changes
   - Link related issues
   - Ensure CI checks pass

## 📋 Coding Standards

### Smart Contracts (Solidity)

- Follow [Solidity Style Guide](https://docs.soliditylang.org/en/latest/style-guide.html)
- Use OpenZeppelin libraries for security
- Include comprehensive NatSpec documentation
- Implement proper access controls
- Add circuit breakers for critical functions

```solidity
/**
 * @title YieldVault
 * @dev ERC-4626 compliant vault with AI-optimized strategies
 * @author Subaskar S
 */
contract YieldVault is ERC4626, AccessControl, Pausable {
    // Clear variable naming
    mapping(address => StrategyInfo) public strategies;
    
    /**
     * @dev Deposits assets and mints shares
     * @param assets Amount of assets to deposit
     * @param receiver Address to receive shares
     */
    function deposit(uint256 assets, address receiver) 
        external 
        override 
        whenNotPaused 
        returns (uint256 shares) 
    {
        // Implementation
    }
}
```

### Backend (Python)

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for all functions
- Implement proper error handling
- Add comprehensive docstrings
- Use async/await for I/O operations

```python
from typing import List, Optional
import asyncio

class MLService:
    """Machine learning service for yield optimization."""
    
    async def predict_yields(
        self, 
        protocols: List[str], 
        horizon_days: int = 7
    ) -> List[YieldPrediction]:
        """
        Predict yields for given protocols.
        
        Args:
            protocols: List of protocol names
            horizon_days: Prediction horizon in days
            
        Returns:
            List of yield predictions with confidence scores
            
        Raises:
            ValueError: If protocols list is empty
        """
        if not protocols:
            raise ValueError("Protocols list cannot be empty")
        
        # Implementation
```

### Frontend (React/TypeScript)

- Use TypeScript for type safety
- Follow React best practices
- Implement proper error boundaries
- Use meaningful component names
- Add proper prop validation

```typescript
interface VaultCardProps {
  vault: Vault;
  onDeposit: (amount: string) => Promise<void>;
  loading?: boolean;
}

const VaultCard: React.FC<VaultCardProps> = ({ 
  vault, 
  onDeposit, 
  loading = false 
}) => {
  const [depositAmount, setDepositAmount] = useState<string>('');
  
  const handleDeposit = useCallback(async () => {
    try {
      await onDeposit(depositAmount);
      setDepositAmount('');
    } catch (error) {
      console.error('Deposit failed:', error);
    }
  }, [depositAmount, onDeposit]);
  
  return (
    <Card>
      {/* Component implementation */}
    </Card>
  );
};
```

## 🧪 Testing Guidelines

### Test Coverage Requirements

- Smart Contracts: 95%+ line coverage
- Backend API: 90%+ line coverage
- Frontend Components: 85%+ line coverage
- ML Models: 80%+ function coverage

### Writing Tests

**Smart Contract Tests:**
```javascript
describe("YieldVault", function () {
  it("should allow deposits and mint correct shares", async function () {
    const depositAmount = ethers.utils.parseEther("100");
    
    await asset.connect(user1).approve(vault.address, depositAmount);
    await expect(vault.connect(user1).deposit(depositAmount, user1.address))
      .to.emit(vault, "Deposit")
      .withArgs(user1.address, user1.address, depositAmount, depositAmount);
    
    expect(await vault.balanceOf(user1.address)).to.equal(depositAmount);
  });
});
```

**Backend Tests:**
```python
@pytest.mark.asyncio
async def test_predict_yields_success(mock_ml_service):
    """Test successful yield prediction."""
    protocols = ["compound", "aave"]
    
    predictions = await mock_ml_service.predict_yields(protocols)
    
    assert len(predictions) == 2
    assert all(p.confidence > 0.5 for p in predictions)
```

**Frontend Tests:**
```typescript
describe('Dashboard Component', () => {
  it('displays portfolio metrics correctly', async () => {
    render(<Dashboard />);
    
    await waitFor(() => {
      expect(screen.getByText('Total Portfolio Value')).toBeInTheDocument();
      expect(screen.getByText('$50,000.00')).toBeInTheDocument();
    });
  });
});
```

## 🔒 Security Guidelines

### Security Best Practices

1. **Smart Contracts**
   - Use OpenZeppelin libraries
   - Implement reentrancy guards
   - Add proper access controls
   - Include circuit breakers
   - Get security audits

2. **Backend**
   - Validate all inputs
   - Use parameterized queries
   - Implement rate limiting
   - Secure API endpoints
   - Handle errors gracefully

3. **Frontend**
   - Sanitize user inputs
   - Implement CSP headers
   - Use HTTPS only
   - Validate wallet connections
   - Handle private keys securely

### Reporting Security Issues

If you discover a security vulnerability, please:

1. **DO NOT** create a public issue
2. Email security concerns to: security@yieldfarm.ai
3. Include detailed description and reproduction steps
4. Allow time for investigation and fix before disclosure

## 📚 Documentation Standards

### Code Documentation

- Add clear comments for complex logic
- Use proper docstrings/NatSpec
- Include examples in documentation
- Keep documentation up to date

### API Documentation

- Document all endpoints
- Include request/response examples
- Specify error codes and messages
- Add authentication requirements

## 🎉 Recognition

Contributors will be recognized in:

- README.md contributors section
- Release notes for significant contributions
- Project documentation
- Community announcements

## 📞 Getting Help

- **Discord**: Join our [Discord server](https://discord.gg/yieldfarm)
- **GitHub Issues**: Create an issue for bugs or questions
- **Discussions**: Use GitHub Discussions for general questions
- **Email**: Contact maintainers at dev@yieldfarm.ai

## 📋 Issue Templates

When creating issues, please use our templates:

- **Bug Report**: Include reproduction steps and environment details
- **Feature Request**: Describe the feature and its benefits
- **Security Issue**: Use private reporting for security concerns

## 🚀 Development Roadmap

Check our [project roadmap](https://github.com/Subaskar-S/ai-yield-farming/projects) to see:

- Planned features
- Current priorities
- Areas needing help
- Long-term vision

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to the future of DeFi! 🚀

**Made with ❤️ by [Subaskar S](https://github.com/Subaskar-S)**
