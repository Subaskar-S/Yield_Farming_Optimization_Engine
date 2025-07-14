// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "@openzeppelin/contracts/interfaces/IERC4626.sol";

import "../interfaces/IYieldVault.sol";
import "../interfaces/IStrategy.sol";
import "../security/CircuitBreaker.sol";

/**
 * @title YieldVault
 * @dev AI-driven yield farming vault implementing ERC-4626 standard
 */
contract YieldVault is 
    ERC20, 
    IERC4626, 
    IYieldVault, 
    ReentrancyGuard, 
    Pausable, 
    AccessControl,
    CircuitBreaker 
{
    using SafeERC20 for IERC20;
    using Math for uint256;

    // Constants
    bytes32 public constant MANAGER_ROLE = keccak256("MANAGER_ROLE");
    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");
    
    uint256 public constant MAX_BPS = 10000;
    uint256 public constant MAX_PERFORMANCE_FEE = 2000; // 20%
    uint256 public constant MAX_MANAGEMENT_FEE = 200;   // 2%
    uint256 public constant REBALANCE_COOLDOWN = 1 hours;

    // State variables
    IERC20 private immutable _asset;
    RiskProfile public riskProfile;
    VaultStatus public status;
    
    uint256 public performanceFee; // In basis points
    uint256 public managementFee;  // In basis points
    uint256 public lastRebalance;
    uint256 public totalYieldGenerated;
    uint256 public feeCollected;
    
    address public feeRecipient;
    
    // Strategy management
    StrategyAllocation[] public strategies;
    mapping(address => uint256) public strategyIndex;
    mapping(address => bool) public isStrategy;
    
    // Performance tracking
    uint256 public totalReturn;
    uint256 public maxDrawdown;
    uint256 private _lastTotalAssets;

    constructor(
        address asset_,
        string memory name_,
        string memory symbol_,
        RiskProfile riskProfile_,
        address admin,
        address feeRecipient_
    ) ERC20(name_, symbol_) {
        require(asset_ != address(0), "Invalid asset");
        require(admin != address(0), "Invalid admin");
        require(feeRecipient_ != address(0), "Invalid fee recipient");
        
        _asset = IERC20(asset_);
        riskProfile = riskProfile_;
        status = VaultStatus.ACTIVE;
        feeRecipient = feeRecipient_;
        
        performanceFee = 1000; // 10%
        managementFee = 100;   // 1%
        
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(MANAGER_ROLE, admin);
        _grantRole(EMERGENCY_ROLE, admin);
        
        lastRebalance = block.timestamp;
    }

    // ERC4626 Implementation
    function asset() public view override returns (address) {
        return address(_asset);
    }

    function totalAssets() public view override returns (uint256) {
        uint256 total = _asset.balanceOf(address(this));
        
        for (uint256 i = 0; i < strategies.length; i++) {
            if (strategies[i].active) {
                total += IStrategy(strategies[i].strategy).estimatedTotalAssets();
            }
        }
        
        return total;
    }

    function convertToShares(uint256 assets) public view override returns (uint256) {
        return _convertToShares(assets, Math.Rounding.Down);
    }

    function convertToAssets(uint256 shares) public view override returns (uint256) {
        return _convertToAssets(shares, Math.Rounding.Down);
    }

    function maxDeposit(address) public view override returns (uint256) {
        return status == VaultStatus.ACTIVE ? type(uint256).max : 0;
    }

    function maxMint(address) public view override returns (uint256) {
        return status == VaultStatus.ACTIVE ? type(uint256).max : 0;
    }

    function maxWithdraw(address owner) public view override returns (uint256) {
        return _convertToAssets(balanceOf(owner), Math.Rounding.Down);
    }

    function maxRedeem(address owner) public view override returns (uint256) {
        return balanceOf(owner);
    }

    function previewDeposit(uint256 assets) public view override returns (uint256) {
        return _convertToShares(assets, Math.Rounding.Down);
    }

    function previewMint(uint256 shares) public view override returns (uint256) {
        return _convertToAssets(shares, Math.Rounding.Up);
    }

    function previewWithdraw(uint256 assets) public view override returns (uint256) {
        return _convertToShares(assets, Math.Rounding.Up);
    }

    function previewRedeem(uint256 shares) public view override returns (uint256) {
        return _convertToAssets(shares, Math.Rounding.Down);
    }

    function deposit(uint256 assets, address receiver) 
        public 
        override 
        nonReentrant 
        whenNotPaused 
        returns (uint256) 
    {
        require(assets > 0, "Cannot deposit 0");
        require(status == VaultStatus.ACTIVE, "Vault not active");
        
        uint256 shares = previewDeposit(assets);
        
        _asset.safeTransferFrom(msg.sender, address(this), assets);
        _mint(receiver, shares);
        
        emit Deposit(msg.sender, receiver, assets, shares);
        
        return shares;
    }

    function mint(uint256 shares, address receiver) 
        public 
        override 
        nonReentrant 
        whenNotPaused 
        returns (uint256) 
    {
        require(shares > 0, "Cannot mint 0");
        require(status == VaultStatus.ACTIVE, "Vault not active");
        
        uint256 assets = previewMint(shares);
        
        _asset.safeTransferFrom(msg.sender, address(this), assets);
        _mint(receiver, shares);
        
        emit Deposit(msg.sender, receiver, assets, shares);
        
        return assets;
    }

    function withdraw(uint256 assets, address receiver, address owner) 
        public 
        override 
        nonReentrant 
        returns (uint256) 
    {
        require(assets > 0, "Cannot withdraw 0");
        
        uint256 shares = previewWithdraw(assets);
        
        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, shares);
        }
        
        _burn(owner, shares);
        
        // Withdraw from strategies if needed
        uint256 availableAssets = _asset.balanceOf(address(this));
        if (availableAssets < assets) {
            _withdrawFromStrategies(assets - availableAssets);
        }
        
        _asset.safeTransfer(receiver, assets);
        
        emit Withdraw(msg.sender, receiver, owner, assets, shares);
        
        return shares;
    }

    function redeem(uint256 shares, address receiver, address owner) 
        public 
        override 
        nonReentrant 
        returns (uint256) 
    {
        require(shares > 0, "Cannot redeem 0");
        
        if (msg.sender != owner) {
            _spendAllowance(owner, msg.sender, shares);
        }
        
        uint256 assets = previewRedeem(shares);
        
        _burn(owner, shares);
        
        // Withdraw from strategies if needed
        uint256 availableAssets = _asset.balanceOf(address(this));
        if (availableAssets < assets) {
            _withdrawFromStrategies(assets - availableAssets);
        }
        
        _asset.safeTransfer(receiver, assets);
        
        emit Withdraw(msg.sender, receiver, owner, assets, shares);
        
        return assets;
    }

    // Internal helper functions
    function _convertToShares(uint256 assets, Math.Rounding rounding) 
        internal 
        view 
        returns (uint256) 
    {
        uint256 supply = totalSupply();
        return (assets == 0 || supply == 0) 
            ? assets 
            : assets.mulDiv(supply, totalAssets(), rounding);
    }

    function _convertToAssets(uint256 shares, Math.Rounding rounding) 
        internal 
        view 
        returns (uint256) 
    {
        uint256 supply = totalSupply();
        return (supply == 0) 
            ? shares 
            : shares.mulDiv(totalAssets(), supply, rounding);
    }

    function _withdrawFromStrategies(uint256 amount) internal {
        uint256 remaining = amount;
        
        for (uint256 i = 0; i < strategies.length && remaining > 0; i++) {
            if (!strategies[i].active) continue;
            
            IStrategy strategy = IStrategy(strategies[i].strategy);
            uint256 strategyBalance = strategy.balanceOf();
            
            if (strategyBalance > 0) {
                uint256 toWithdraw = Math.min(remaining, strategyBalance);
                uint256 withdrawn = strategy.withdraw(toWithdraw);
                remaining -= withdrawn;
            }
        }
    }

    // IYieldVault Implementation
    function getVaultInfo() external view override returns (VaultInfo memory) {
        return VaultInfo({
            name: name(),
            symbol: symbol(),
            asset: address(_asset),
            riskProfile: riskProfile,
            status: status,
            totalAssets: totalAssets(),
            totalShares: totalSupply(),
            lastRebalance: lastRebalance,
            performanceFee: performanceFee,
            managementFee: managementFee
        });
    }

    function getRiskProfile() external view override returns (RiskProfile) {
        return riskProfile;
    }

    function getStatus() external view override returns (VaultStatus) {
        return status;
    }

    function getStrategies() external view override returns (StrategyAllocation[] memory) {
        return strategies;
    }

    function getStrategy(address strategy) external view override returns (StrategyAllocation memory) {
        require(isStrategy[strategy], "Strategy not found");
        return strategies[strategyIndex[strategy]];
    }

    function getTotalYieldGenerated() external view override returns (uint256) {
        return totalYieldGenerated;
    }

    function getAPY() external view override returns (uint256) {
        if (totalSupply() == 0 || totalReturn == 0) return 0;

        // Simple APY calculation - can be enhanced with more sophisticated methods
        uint256 timeElapsed = block.timestamp - lastRebalance;
        if (timeElapsed == 0) return 0;

        uint256 annualizedReturn = (totalReturn * 365 days) / timeElapsed;
        return (annualizedReturn * MAX_BPS) / totalAssets();
    }

    function getLastRebalanceTime() external view override returns (uint256) {
        return lastRebalance;
    }

    function canRebalance() external view override returns (bool) {
        return block.timestamp >= lastRebalance + REBALANCE_COOLDOWN;
    }

    function getPerformanceMetrics() external view override returns (
        uint256 totalReturn_,
        uint256 annualizedReturn_,
        uint256 sharpeRatio_,
        uint256 maxDrawdown_
    ) {
        totalReturn_ = totalReturn;

        uint256 timeElapsed = block.timestamp - lastRebalance;
        if (timeElapsed > 0) {
            annualizedReturn_ = (totalReturn * 365 days) / timeElapsed;
        }

        // Simplified metrics - can be enhanced with more sophisticated calculations
        sharpeRatio_ = annualizedReturn_ > 0 ? (annualizedReturn_ * 100) / (annualizedReturn_ + 100) : 0;
        maxDrawdown_ = maxDrawdown;
    }

    // Strategy Management
    function addStrategy(address strategy, uint256 allocation)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        require(strategy != address(0), "Invalid strategy");
        require(allocation <= MAX_BPS, "Allocation too high");
        require(!isStrategy[strategy], "Strategy already exists");

        // Verify total allocation doesn't exceed 100%
        uint256 totalAllocation = allocation;
        for (uint256 i = 0; i < strategies.length; i++) {
            if (strategies[i].active) {
                totalAllocation += strategies[i].allocation;
            }
        }
        require(totalAllocation <= MAX_BPS, "Total allocation exceeds 100%");

        strategies.push(StrategyAllocation({
            strategy: strategy,
            allocation: allocation,
            assets: 0,
            active: true
        }));

        strategyIndex[strategy] = strategies.length - 1;
        isStrategy[strategy] = true;

        // Set vault in strategy
        IStrategy(strategy).setVault(address(this));

        emit StrategyUpdated(address(0), strategy);
    }

    function removeStrategy(address strategy)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        require(isStrategy[strategy], "Strategy not found");

        uint256 index = strategyIndex[strategy];
        StrategyAllocation storage strategyAlloc = strategies[index];

        // Withdraw all assets from strategy
        if (strategyAlloc.assets > 0) {
            IStrategy(strategy).withdrawAll();
        }

        strategyAlloc.active = false;
        strategyAlloc.allocation = 0;
        strategyAlloc.assets = 0;

        isStrategy[strategy] = false;

        emit StrategyUpdated(strategy, address(0));
    }

    function updateStrategyAllocation(address strategy, uint256 newAllocation)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        require(isStrategy[strategy], "Strategy not found");
        require(newAllocation <= MAX_BPS, "Allocation too high");

        uint256 index = strategyIndex[strategy];
        uint256 oldAllocation = strategies[index].allocation;

        // Verify total allocation doesn't exceed 100%
        uint256 totalAllocation = newAllocation;
        for (uint256 i = 0; i < strategies.length; i++) {
            if (i != index && strategies[i].active) {
                totalAllocation += strategies[i].allocation;
            }
        }
        require(totalAllocation <= MAX_BPS, "Total allocation exceeds 100%");

        strategies[index].allocation = newAllocation;

        emit StrategyUpdated(strategy, strategy);
    }

    function rebalance() external override onlyRole(KEEPER_ROLE) {
        require(canRebalance(), "Rebalance cooldown active");
        require(status == VaultStatus.ACTIVE, "Vault not active");

        uint256 totalVaultAssets = totalAssets();
        uint256 availableAssets = _asset.balanceOf(address(this));

        // Rebalance each active strategy
        for (uint256 i = 0; i < strategies.length; i++) {
            if (!strategies[i].active) continue;

            StrategyAllocation storage strategyAlloc = strategies[i];
            uint256 targetAssets = (totalVaultAssets * strategyAlloc.allocation) / MAX_BPS;
            uint256 currentAssets = IStrategy(strategyAlloc.strategy).estimatedTotalAssets();

            if (targetAssets > currentAssets) {
                // Need to deposit more
                uint256 toDeposit = targetAssets - currentAssets;
                if (availableAssets >= toDeposit) {
                    _asset.safeTransfer(strategyAlloc.strategy, toDeposit);
                    IStrategy(strategyAlloc.strategy).deposit(toDeposit);
                    availableAssets -= toDeposit;
                }
            } else if (targetAssets < currentAssets) {
                // Need to withdraw some
                uint256 toWithdraw = currentAssets - targetAssets;
                IStrategy(strategyAlloc.strategy).withdraw(toWithdraw);
            }

            strategyAlloc.assets = IStrategy(strategyAlloc.strategy).estimatedTotalAssets();
        }

        lastRebalance = block.timestamp;
        emit Rebalanced(totalVaultAssets, totalVaultAssets);
    }

    function harvestYield() external override onlyRole(KEEPER_ROLE) {
        uint256 totalHarvested = 0;

        for (uint256 i = 0; i < strategies.length; i++) {
            if (!strategies[i].active) continue;

            IStrategy strategy = IStrategy(strategies[i].strategy);
            if (strategy.canHarvest()) {
                uint256 harvested = strategy.harvest();
                totalHarvested += harvested;
            }
        }

        if (totalHarvested > 0) {
            totalYieldGenerated += totalHarvested;

            // Collect performance fee
            uint256 performanceFeeAmount = (totalHarvested * performanceFee) / MAX_BPS;
            if (performanceFeeAmount > 0) {
                _asset.safeTransfer(feeRecipient, performanceFeeAmount);
                feeCollected += performanceFeeAmount;
            }

            emit YieldHarvested(totalHarvested, block.timestamp);
        }
    }

    // Risk Management
    function setRiskProfile(RiskProfile newProfile)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        RiskProfile oldProfile = riskProfile;
        riskProfile = newProfile;
        emit RiskProfileUpdated(oldProfile, newProfile);
    }

    function emergencyPause(string calldata reason)
        external
        override
        onlyRole(EMERGENCY_ROLE)
    {
        status = VaultStatus.EMERGENCY_PAUSE;
        _pause();
        emit EmergencyPaused(msg.sender, reason);
    }

    function emergencyUnpause()
        external
        override
        onlyRole(EMERGENCY_ROLE)
    {
        status = VaultStatus.ACTIVE;
        _unpause();
        emit EmergencyUnpaused(msg.sender);
    }

    function emergencyWithdraw(address to)
        external
        override
        onlyRole(EMERGENCY_ROLE)
    {
        require(to != address(0), "Invalid recipient");

        // Withdraw from all strategies
        for (uint256 i = 0; i < strategies.length; i++) {
            if (strategies[i].active) {
                IStrategy(strategies[i].strategy).emergencyExit();
            }
        }

        // Transfer all assets to recipient
        uint256 balance = _asset.balanceOf(address(this));
        if (balance > 0) {
            _asset.safeTransfer(to, balance);
        }

        status = VaultStatus.DEPRECATED;
    }

    // Fee Management
    function setPerformanceFee(uint256 newFee)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        require(newFee <= MAX_PERFORMANCE_FEE, "Fee too high");
        performanceFee = newFee;
    }

    function setManagementFee(uint256 newFee)
        external
        override
        onlyRole(MANAGER_ROLE)
    {
        require(newFee <= MAX_MANAGEMENT_FEE, "Fee too high");
        managementFee = newFee;
    }

    function collectFees() external override onlyRole(MANAGER_ROLE) {
        uint256 totalAssets_ = totalAssets();
        uint256 managementFeeAmount = (totalAssets_ * managementFee) / MAX_BPS / 365; // Daily fee

        if (managementFeeAmount > 0) {
            uint256 availableAssets = _asset.balanceOf(address(this));
            if (availableAssets < managementFeeAmount) {
                _withdrawFromStrategies(managementFeeAmount - availableAssets);
            }

            _asset.safeTransfer(feeRecipient, managementFeeAmount);
            feeCollected += managementFeeAmount;
        }
    }

    // Circuit Breaker Integration
    function _checkCircuitBreaker() internal view {
        uint256 currentAssets = totalAssets();
        if (_lastTotalAssets > 0) {
            uint256 loss = _lastTotalAssets > currentAssets ?
                _lastTotalAssets - currentAssets : 0;

            if (loss > 0) {
                uint256 lossPercentage = (loss * MAX_BPS) / _lastTotalAssets;
                require(!shouldTriggerCircuitBreaker(lossPercentage), "Circuit breaker triggered");
            }
        }
    }

    function _updatePerformanceMetrics() internal {
        uint256 currentAssets = totalAssets();

        if (_lastTotalAssets > 0) {
            if (currentAssets > _lastTotalAssets) {
                totalReturn += currentAssets - _lastTotalAssets;
            } else {
                uint256 drawdown = _lastTotalAssets - currentAssets;
                if (drawdown > maxDrawdown) {
                    maxDrawdown = drawdown;
                }
            }
        }

        _lastTotalAssets = currentAssets;
    }

    // Admin functions
    function setFeeRecipient(address newRecipient)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(newRecipient != address(0), "Invalid recipient");
        feeRecipient = newRecipient;
    }

    function pause() external onlyRole(EMERGENCY_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(EMERGENCY_ROLE) {
        _unpause();
    }

    // Override functions to add circuit breaker checks
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 amount
    ) internal override {
        super._beforeTokenTransfer(from, to, amount);

        if (from != address(0) && to != address(0)) {
            _checkCircuitBreaker();
        }

        _updatePerformanceMetrics();
    }

    // View functions for external integrations
    function decimals() public view override returns (uint8) {
        return IERC20Metadata(address(_asset)).decimals();
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(AccessControl)
        returns (bool)
    {
        return interfaceId == type(IERC4626).interfaceId ||
               interfaceId == type(IYieldVault).interfaceId ||
               super.supportsInterface(interfaceId);
    }
}
