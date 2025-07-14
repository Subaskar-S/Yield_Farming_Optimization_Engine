// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

import "../interfaces/IStrategy.sol";
import "../interfaces/IYieldVault.sol";

/**
 * @title BaseStrategy
 * @dev Abstract base contract for all yield farming strategies
 */
abstract contract BaseStrategy is IStrategy, ReentrancyGuard, Pausable, AccessControl {
    using SafeERC20 for IERC20;
    using Math for uint256;

    // Constants
    bytes32 public constant VAULT_ROLE = keccak256("VAULT_ROLE");
    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant MANAGER_ROLE = keccak256("MANAGER_ROLE");
    
    uint256 public constant MAX_BPS = 10000;
    uint256 public constant MAX_SLIPPAGE = 1000; // 10%
    uint256 public constant MIN_HARVEST_AMOUNT = 1e15; // 0.001 tokens

    // State variables
    IERC20 public immutable want; // The token this strategy farms
    address public vault;
    StrategyStatus public status;
    
    string public strategyName;
    string public protocolName;
    
    uint256 public totalDeposited;
    uint256 public totalYieldGenerated;
    uint256 public lastHarvest;
    uint256 public riskScore; // 0-100, higher = riskier
    uint256 public expectedAPY; // In basis points
    
    // Risk management
    uint256 public maxSlippage;
    uint256 public minHarvestAmount;
    uint256 public maxSingleDeposit;
    uint256 public maxTotalDeposits;
    
    // Performance tracking
    uint256 public totalReturn;
    uint256 public totalLoss;
    uint256 public harvestCount;
    uint256 public lastProfitReport;

    // Events
    event StrategyInitialized(address indexed vault, address indexed want);
    event MaxSlippageUpdated(uint256 oldSlippage, uint256 newSlippage);
    event MinHarvestAmountUpdated(uint256 oldAmount, uint256 newAmount);
    event RiskScoreUpdated(uint256 oldScore, uint256 newScore);

    modifier onlyVault() {
        require(msg.sender == vault, "Only vault");
        _;
    }

    modifier onlyVaultOrKeeper() {
        require(
            msg.sender == vault || hasRole(KEEPER_ROLE, msg.sender),
            "Only vault or keeper"
        );
        _;
    }

    constructor(
        address _want,
        address _vault,
        string memory _strategyName,
        string memory _protocolName,
        uint256 _riskScore
    ) {
        require(_want != address(0), "Invalid want token");
        require(_vault != address(0), "Invalid vault");
        require(_riskScore <= 100, "Invalid risk score");
        
        want = IERC20(_want);
        vault = _vault;
        strategyName = _strategyName;
        protocolName = _protocolName;
        riskScore = _riskScore;
        status = StrategyStatus.ACTIVE;
        
        // Default risk management settings
        maxSlippage = 300; // 3%
        minHarvestAmount = MIN_HARVEST_AMOUNT;
        maxSingleDeposit = type(uint256).max;
        maxTotalDeposits = type(uint256).max;
        
        // Set up roles
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(VAULT_ROLE, _vault);
        _grantRole(MANAGER_ROLE, msg.sender);
        
        lastHarvest = block.timestamp;
        
        emit StrategyInitialized(_vault, _want);
    }

    // IStrategy Implementation
    function getStrategyInfo() external view override returns (StrategyInfo memory) {
        return StrategyInfo({
            name: strategyName,
            protocol: protocolName,
            asset: address(want),
            status: status,
            totalDeposited: totalDeposited,
            totalYieldGenerated: totalYieldGenerated,
            lastHarvest: lastHarvest,
            riskScore: riskScore,
            expectedAPY: expectedAPY
        });
    }

    function getPerformanceMetrics() external view override returns (PerformanceMetrics memory) {
        uint256 totalAssets = estimatedTotalAssets();
        uint256 timeElapsed = block.timestamp - lastProfitReport;
        
        uint256 annualizedReturn = 0;
        if (timeElapsed > 0 && totalDeposited > 0) {
            annualizedReturn = (totalReturn * 365 days * MAX_BPS) / (timeElapsed * totalDeposited);
        }
        
        // Simplified metrics - can be enhanced
        uint256 volatility = _calculateVolatility();
        uint256 sharpeRatio = annualizedReturn > volatility ? 
            ((annualizedReturn - volatility) * 100) / volatility : 0;
        
        return PerformanceMetrics({
            totalReturn: totalReturn,
            annualizedReturn: annualizedReturn,
            volatility: volatility,
            sharpeRatio: sharpeRatio,
            maxDrawdown: totalLoss,
            winRate: harvestCount > 0 ? (harvestCount * MAX_BPS) / (harvestCount + 1) : 0
        });
    }

    function getAsset() external view override returns (address) {
        return address(want);
    }

    function getVault() external view override returns (address) {
        return vault;
    }

    function balanceOf() public view override returns (uint256) {
        return balanceOfWant() + balanceOfPool();
    }

    function balanceOfWant() public view override returns (uint256) {
        return want.balanceOf(address(this));
    }

    function isActive() external view override returns (bool) {
        return status == StrategyStatus.ACTIVE;
    }

    function getRiskScore() external view override returns (uint256) {
        return riskScore;
    }

    // Core functions - to be implemented by specific strategies
    function balanceOfPool() public view virtual override returns (uint256);
    function estimatedTotalAssets() public view virtual override returns (uint256);
    function canHarvest() public view virtual override returns (bool);
    function expectedReturn() public view virtual override returns (uint256);

    function deposit(uint256 amount) external virtual override onlyVault nonReentrant whenNotPaused {
        require(amount > 0, "Cannot deposit 0");
        require(status == StrategyStatus.ACTIVE, "Strategy not active");
        require(amount <= maxSingleDeposit, "Exceeds max single deposit");
        require(totalDeposited + amount <= maxTotalDeposits, "Exceeds max total deposits");
        
        want.safeTransferFrom(vault, address(this), amount);
        
        _deposit(amount);
        
        totalDeposited += amount;
        emit Deposited(amount, block.timestamp);
    }

    function withdraw(uint256 amount) external virtual override onlyVault nonReentrant returns (uint256) {
        require(amount > 0, "Cannot withdraw 0");
        
        uint256 withdrawn = _withdraw(amount);
        
        if (withdrawn > 0) {
            want.safeTransfer(vault, withdrawn);
            if (withdrawn <= totalDeposited) {
                totalDeposited -= withdrawn;
            } else {
                totalDeposited = 0;
            }
        }
        
        emit Withdrawn(withdrawn, block.timestamp);
        return withdrawn;
    }

    function withdrawAll() external virtual override onlyVault nonReentrant returns (uint256) {
        uint256 totalAssets = estimatedTotalAssets();
        uint256 withdrawn = _withdrawAll();
        
        if (withdrawn > 0) {
            want.safeTransfer(vault, withdrawn);
        }
        
        totalDeposited = 0;
        emit Withdrawn(withdrawn, block.timestamp);
        return withdrawn;
    }

    function harvest() external virtual override onlyVaultOrKeeper nonReentrant whenNotPaused returns (uint256) {
        require(canHarvest(), "Cannot harvest yet");
        require(status == StrategyStatus.ACTIVE, "Strategy not active");
        
        uint256 beforeBalance = want.balanceOf(address(this));
        uint256 harvested = _harvest();
        uint256 afterBalance = want.balanceOf(address(this));
        
        // Verify harvest amount
        uint256 actualHarvested = afterBalance - beforeBalance;
        require(actualHarvested >= minHarvestAmount, "Harvest amount too small");
        
        totalYieldGenerated += actualHarvested;
        totalReturn += actualHarvested;
        harvestCount++;
        lastHarvest = block.timestamp;
        lastProfitReport = block.timestamp;
        
        // Transfer harvested tokens to vault
        if (actualHarvested > 0) {
            want.safeTransfer(vault, actualHarvested);
        }
        
        emit YieldHarvested(actualHarvested, block.timestamp);
        return actualHarvested;
    }

    function emergencyExit() external virtual override onlyRole(MANAGER_ROLE) returns (uint256) {
        status = StrategyStatus.EMERGENCY;
        _pause();
        
        uint256 recovered = _emergencyExit();
        
        if (recovered > 0) {
            want.safeTransfer(vault, recovered);
        }
        
        emit EmergencyExited(recovered);
        return recovered;
    }

    // Strategy management
    function setVault(address _vault) external virtual override onlyRole(DEFAULT_ADMIN_ROLE) {
        require(_vault != address(0), "Invalid vault");
        
        _revokeRole(VAULT_ROLE, vault);
        vault = _vault;
        _grantRole(VAULT_ROLE, _vault);
    }

    function pause() external override onlyRole(MANAGER_ROLE) {
        status = StrategyStatus.PAUSED;
        _pause();
    }

    function unpause() external override onlyRole(MANAGER_ROLE) {
        status = StrategyStatus.ACTIVE;
        _unpause();
    }

    function retire() external override onlyRole(MANAGER_ROLE) {
        status = StrategyStatus.DEPRECATED;
        _pause();
    }

    // Risk management
    function setMaxSlippage(uint256 slippage) external override onlyRole(MANAGER_ROLE) {
        require(slippage <= MAX_SLIPPAGE, "Slippage too high");
        
        uint256 oldSlippage = maxSlippage;
        maxSlippage = slippage;
        
        emit MaxSlippageUpdated(oldSlippage, slippage);
    }

    function setMinHarvestAmount(uint256 amount) external override onlyRole(MANAGER_ROLE) {
        uint256 oldAmount = minHarvestAmount;
        minHarvestAmount = amount;
        
        emit MinHarvestAmountUpdated(oldAmount, amount);
    }

    function updateRiskScore(uint256 newScore) external override onlyRole(MANAGER_ROLE) {
        require(newScore <= 100, "Invalid risk score");
        
        uint256 oldScore = riskScore;
        riskScore = newScore;
        
        emit RiskScoreUpdated(oldScore, newScore);
    }

    // Internal functions to be implemented by specific strategies
    function _deposit(uint256 amount) internal virtual;
    function _withdraw(uint256 amount) internal virtual returns (uint256);
    function _withdrawAll() internal virtual returns (uint256);
    function _harvest() internal virtual returns (uint256);
    function _emergencyExit() internal virtual returns (uint256);

    // Helper functions
    function _calculateVolatility() internal view virtual returns (uint256) {
        // Simplified volatility calculation
        // In a real implementation, this would use historical price data
        return riskScore * 10; // Basic approximation
    }

    function _checkSlippage(uint256 expected, uint256 actual) internal view {
        if (expected > 0) {
            uint256 slippage = expected > actual ? 
                ((expected - actual) * MAX_BPS) / expected : 0;
            require(slippage <= maxSlippage, "Slippage too high");
        }
    }

    // Protocol-specific functions (to be implemented by each strategy)
    function getProtocolInfo() external view virtual override returns (
        string memory protocolName_,
        string memory version,
        address protocolAddress
    );
    
    function getRewards() external view virtual override returns (
        address[] memory tokens, 
        uint256[] memory amounts
    );
    
    function claimRewards() external virtual override;
}
