// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "./BaseStrategy.sol";

// Compound protocol interfaces
interface ICToken {
    function mint(uint256 mintAmount) external returns (uint256);
    function redeem(uint256 redeemTokens) external returns (uint256);
    function redeemUnderlying(uint256 redeemAmount) external returns (uint256);
    function balanceOf(address owner) external view returns (uint256);
    function balanceOfUnderlying(address owner) external returns (uint256);
    function exchangeRateStored() external view returns (uint256);
    function supplyRatePerBlock() external view returns (uint256);
    function underlying() external view returns (address);
}

interface IComptroller {
    function claimComp(address holder) external;
    function getCompAddress() external view returns (address);
    function compSpeeds(address cToken) external view returns (uint256);
}

/**
 * @title CompoundStrategy
 * @dev Yield farming strategy for Compound protocol
 */
contract CompoundStrategy is BaseStrategy {
    // Compound protocol contracts
    ICToken public immutable cToken;
    IComptroller public immutable comptroller;
    IERC20 public immutable compToken;
    
    // Strategy specific settings
    uint256 public minCompoundAmount;
    uint256 public lastCompoundTime;
    uint256 public compoundFrequency;
    
    // Events
    event CompoundDeposit(uint256 amount, uint256 cTokensMinted);
    event CompoundWithdraw(uint256 amount, uint256 cTokensRedeemed);
    event CompRewardsClaimed(uint256 amount);
    event AutoCompounded(uint256 compAmount, uint256 underlyingAmount);

    constructor(
        address _want,
        address _vault,
        address _cToken,
        address _comptroller,
        string memory _strategyName
    ) BaseStrategy(
        _want,
        _vault,
        _strategyName,
        "Compound",
        25 // Medium risk score for Compound
    ) {
        require(_cToken != address(0), "Invalid cToken");
        require(_comptroller != address(0), "Invalid comptroller");
        
        cToken = ICToken(_cToken);
        comptroller = IComptroller(_comptroller);
        compToken = IERC20(comptroller.getCompAddress());
        
        // Verify cToken underlying matches want token
        require(cToken.underlying() == _want, "cToken underlying mismatch");
        
        // Strategy specific settings
        minCompoundAmount = 1e15; // 0.001 tokens minimum to compound
        compoundFrequency = 1 days; // Compound rewards daily
        lastCompoundTime = block.timestamp;
        
        // Set expected APY based on current supply rate
        expectedAPY = _calculateExpectedAPY();
        
        // Approve cToken to spend want tokens
        want.safeApprove(_cToken, type(uint256).max);
    }

    // View functions
    function balanceOfPool() public view override returns (uint256) {
        uint256 cTokenBalance = cToken.balanceOf(address(this));
        if (cTokenBalance == 0) return 0;
        
        uint256 exchangeRate = cToken.exchangeRateStored();
        return (cTokenBalance * exchangeRate) / 1e18;
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return balanceOfWant() + balanceOfPool();
    }

    function canHarvest() public view override returns (bool) {
        // Can harvest if:
        // 1. Enough time has passed since last harvest
        // 2. There are COMP rewards to claim
        // 3. Strategy is active
        return (block.timestamp >= lastHarvest + compoundFrequency) &&
               _getClaimableComp() >= minCompoundAmount &&
               status == StrategyStatus.ACTIVE;
    }

    function expectedReturn() public view override returns (uint256) {
        uint256 supplyRate = cToken.supplyRatePerBlock();
        uint256 blocksPerYear = 2102400; // Approximate blocks per year
        uint256 currentBalance = balanceOfPool();
        
        if (currentBalance == 0) return 0;
        
        // Calculate expected return from supply rate
        uint256 supplyReturn = (currentBalance * supplyRate * blocksPerYear) / 1e18;
        
        // Add expected COMP rewards
        uint256 compRewards = _estimateCompRewards();
        
        return supplyReturn + compRewards;
    }

    // Core strategy functions
    function _deposit(uint256 amount) internal override {
        require(amount > 0, "Cannot deposit 0");
        
        uint256 beforeCTokens = cToken.balanceOf(address(this));
        
        // Mint cTokens
        uint256 result = cToken.mint(amount);
        require(result == 0, "Compound mint failed");
        
        uint256 afterCTokens = cToken.balanceOf(address(this));
        uint256 cTokensMinted = afterCTokens - beforeCTokens;
        
        emit CompoundDeposit(amount, cTokensMinted);
    }

    function _withdraw(uint256 amount) internal override returns (uint256) {
        if (amount == 0) return 0;
        
        uint256 beforeBalance = want.balanceOf(address(this));
        
        // Redeem underlying tokens
        uint256 result = cToken.redeemUnderlying(amount);
        require(result == 0, "Compound redeem failed");
        
        uint256 afterBalance = want.balanceOf(address(this));
        uint256 withdrawn = afterBalance - beforeBalance;
        
        emit CompoundWithdraw(withdrawn, 0);
        return withdrawn;
    }

    function _withdrawAll() internal override returns (uint256) {
        uint256 cTokenBalance = cToken.balanceOf(address(this));
        if (cTokenBalance == 0) return 0;
        
        uint256 beforeBalance = want.balanceOf(address(this));
        
        // Redeem all cTokens
        uint256 result = cToken.redeem(cTokenBalance);
        require(result == 0, "Compound redeem all failed");
        
        uint256 afterBalance = want.balanceOf(address(this));
        uint256 withdrawn = afterBalance - beforeBalance;
        
        emit CompoundWithdraw(withdrawn, cTokenBalance);
        return withdrawn;
    }

    function _harvest() internal override returns (uint256) {
        // Claim COMP rewards
        comptroller.claimComp(address(this));
        
        uint256 compBalance = compToken.balanceOf(address(this));
        if (compBalance < minCompoundAmount) return 0;
        
        // Convert COMP to underlying token
        uint256 underlyingAmount = _swapCompToUnderlying(compBalance);
        
        if (underlyingAmount > 0) {
            // Re-deposit the harvested tokens
            _deposit(underlyingAmount);
            lastCompoundTime = block.timestamp;
            
            emit CompRewardsClaimed(compBalance);
            emit AutoCompounded(compBalance, underlyingAmount);
        }
        
        return underlyingAmount;
    }

    function _emergencyExit() internal override returns (uint256) {
        // Withdraw all funds from Compound
        uint256 withdrawn = _withdrawAll();
        
        // Also claim any pending COMP rewards
        comptroller.claimComp(address(this));
        uint256 compBalance = compToken.balanceOf(address(this));
        
        if (compBalance > 0) {
            // Transfer COMP tokens to vault (don't swap in emergency)
            compToken.safeTransfer(vault, compBalance);
        }
        
        return withdrawn;
    }

    // Protocol-specific functions
    function getProtocolInfo() external view override returns (
        string memory protocolName_,
        string memory version,
        address protocolAddress
    ) {
        return ("Compound", "v2", address(comptroller));
    }

    function getRewards() external view override returns (
        address[] memory tokens,
        uint256[] memory amounts
    ) {
        tokens = new address[](1);
        amounts = new uint256[](1);
        
        tokens[0] = address(compToken);
        amounts[0] = _getClaimableComp();
    }

    function claimRewards() external override onlyVaultOrKeeper {
        comptroller.claimComp(address(this));
        
        uint256 compBalance = compToken.balanceOf(address(this));
        if (compBalance > 0) {
            compToken.safeTransfer(vault, compBalance);
            emit CompRewardsClaimed(compBalance);
        }
    }

    // Internal helper functions
    function _getClaimableComp() internal view returns (uint256) {
        // This is a simplified calculation
        // In practice, you'd need to calculate accrued COMP rewards
        uint256 compSpeed = comptroller.compSpeeds(address(cToken));
        uint256 timeSinceLastClaim = block.timestamp - lastCompoundTime;
        uint256 blocksElapsed = timeSinceLastClaim / 12; // ~12 second blocks
        
        return (compSpeed * blocksElapsed * balanceOfPool()) / 1e18;
    }

    function _estimateCompRewards() internal view returns (uint256) {
        uint256 compSpeed = comptroller.compSpeeds(address(cToken));
        uint256 blocksPerYear = 2102400;
        uint256 currentBalance = balanceOfPool();
        
        if (currentBalance == 0 || compSpeed == 0) return 0;
        
        // Estimate annual COMP rewards (simplified)
        uint256 annualCompRewards = (compSpeed * blocksPerYear * currentBalance) / 1e18;
        
        // Convert to underlying token value (simplified 1:1 for now)
        return annualCompRewards;
    }

    function _swapCompToUnderlying(uint256 compAmount) internal returns (uint256) {
        // This is a placeholder for COMP -> underlying token swap
        // In a real implementation, you would integrate with a DEX like Uniswap
        // For now, we'll assume 1:1 conversion for simplicity
        
        // TODO: Implement actual swap logic using Uniswap or similar DEX
        // This would involve:
        // 1. Approve COMP to DEX router
        // 2. Execute swap with slippage protection
        // 3. Return amount of underlying tokens received
        
        return compAmount; // Placeholder
    }

    function _calculateExpectedAPY() internal view returns (uint256) {
        uint256 supplyRate = cToken.supplyRatePerBlock();
        uint256 blocksPerYear = 2102400;
        
        // Convert to APY in basis points
        return (supplyRate * blocksPerYear * MAX_BPS) / 1e18;
    }

    // Admin functions
    function setMinCompoundAmount(uint256 _minAmount) external onlyRole(MANAGER_ROLE) {
        minCompoundAmount = _minAmount;
    }

    function setCompoundFrequency(uint256 _frequency) external onlyRole(MANAGER_ROLE) {
        require(_frequency >= 1 hours, "Frequency too low");
        compoundFrequency = _frequency;
    }

    function updateExpectedAPY() external onlyRole(MANAGER_ROLE) {
        expectedAPY = _calculateExpectedAPY();
    }

    // Emergency functions
    function rescueToken(address token, uint256 amount) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(token != address(want), "Cannot rescue want token");
        require(token != address(cToken), "Cannot rescue cToken");
        
        IERC20(token).safeTransfer(msg.sender, amount);
    }
}
