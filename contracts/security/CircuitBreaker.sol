// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

/**
 * @title CircuitBreaker
 * @dev Circuit breaker pattern implementation for DeFi protocols
 * Automatically pauses operations when certain thresholds are breached
 */
abstract contract CircuitBreaker is AccessControl, Pausable {
    // Events
    event CircuitBreakerTriggered(
        address indexed trigger,
        string reason,
        uint256 lossPercentage,
        uint256 timestamp
    );
    event CircuitBreakerReset(address indexed resetter, uint256 timestamp);
    event ThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);
    event CooldownUpdated(uint256 oldCooldown, uint256 newCooldown);

    // Constants
    bytes32 public constant CIRCUIT_BREAKER_ROLE = keccak256("CIRCUIT_BREAKER_ROLE");
    uint256 public constant MAX_THRESHOLD = 5000; // 50% maximum loss threshold
    uint256 public constant MIN_COOLDOWN = 1 hours;
    uint256 public constant MAX_COOLDOWN = 7 days;

    // State variables
    uint256 public lossThreshold; // In basis points (e.g., 500 = 5%)
    uint256 public cooldownPeriod; // Time before circuit breaker can be reset
    uint256 public lastTriggered; // Timestamp of last trigger
    bool public circuitBreakerActive;
    
    // Tracking variables
    mapping(address => uint256) public triggerCount;
    uint256 public totalTriggers;
    
    struct CircuitBreakerConfig {
        uint256 lossThreshold;
        uint256 cooldownPeriod;
        bool enabled;
    }

    constructor() {
        lossThreshold = 500; // 5% default
        cooldownPeriod = 4 hours; // 4 hours default
        circuitBreakerActive = false;
    }

    /**
     * @dev Check if circuit breaker should be triggered based on loss percentage
     * @param lossPercentage Loss percentage in basis points
     * @return bool Whether circuit breaker should trigger
     */
    function shouldTriggerCircuitBreaker(uint256 lossPercentage) 
        public 
        view 
        returns (bool) 
    {
        return lossPercentage >= lossThreshold && !circuitBreakerActive;
    }

    /**
     * @dev Trigger the circuit breaker
     * @param reason Reason for triggering
     * @param lossPercentage Loss percentage that triggered the breaker
     */
    function triggerCircuitBreaker(string memory reason, uint256 lossPercentage) 
        external 
        onlyRole(CIRCUIT_BREAKER_ROLE) 
    {
        require(!circuitBreakerActive, "Circuit breaker already active");
        require(lossPercentage >= lossThreshold, "Loss threshold not met");
        
        circuitBreakerActive = true;
        lastTriggered = block.timestamp;
        triggerCount[msg.sender]++;
        totalTriggers++;
        
        _pause();
        
        emit CircuitBreakerTriggered(msg.sender, reason, lossPercentage, block.timestamp);
    }

    /**
     * @dev Automatically trigger circuit breaker (internal function)
     * @param lossPercentage Loss percentage in basis points
     */
    function _autoTriggerCircuitBreaker(uint256 lossPercentage) internal {
        if (shouldTriggerCircuitBreaker(lossPercentage)) {
            circuitBreakerActive = true;
            lastTriggered = block.timestamp;
            totalTriggers++;
            
            _pause();
            
            emit CircuitBreakerTriggered(
                address(this), 
                "Automatic trigger due to loss threshold", 
                lossPercentage, 
                block.timestamp
            );
        }
    }

    /**
     * @dev Reset the circuit breaker after cooldown period
     */
    function resetCircuitBreaker() 
        external 
        onlyRole(CIRCUIT_BREAKER_ROLE) 
    {
        require(circuitBreakerActive, "Circuit breaker not active");
        require(
            block.timestamp >= lastTriggered + cooldownPeriod, 
            "Cooldown period not elapsed"
        );
        
        circuitBreakerActive = false;
        _unpause();
        
        emit CircuitBreakerReset(msg.sender, block.timestamp);
    }

    /**
     * @dev Emergency reset (bypasses cooldown) - requires admin role
     */
    function emergencyReset() 
        external 
        onlyRole(DEFAULT_ADMIN_ROLE) 
    {
        require(circuitBreakerActive, "Circuit breaker not active");
        
        circuitBreakerActive = false;
        _unpause();
        
        emit CircuitBreakerReset(msg.sender, block.timestamp);
    }

    /**
     * @dev Update loss threshold
     * @param newThreshold New threshold in basis points
     */
    function setLossThreshold(uint256 newThreshold) 
        external 
        onlyRole(DEFAULT_ADMIN_ROLE) 
    {
        require(newThreshold > 0 && newThreshold <= MAX_THRESHOLD, "Invalid threshold");
        
        uint256 oldThreshold = lossThreshold;
        lossThreshold = newThreshold;
        
        emit ThresholdUpdated(oldThreshold, newThreshold);
    }

    /**
     * @dev Update cooldown period
     * @param newCooldown New cooldown period in seconds
     */
    function setCooldownPeriod(uint256 newCooldown) 
        external 
        onlyRole(DEFAULT_ADMIN_ROLE) 
    {
        require(
            newCooldown >= MIN_COOLDOWN && newCooldown <= MAX_COOLDOWN, 
            "Invalid cooldown"
        );
        
        uint256 oldCooldown = cooldownPeriod;
        cooldownPeriod = newCooldown;
        
        emit CooldownUpdated(oldCooldown, newCooldown);
    }

    /**
     * @dev Get circuit breaker configuration
     * @return CircuitBreakerConfig Current configuration
     */
    function getCircuitBreakerConfig() 
        external 
        view 
        returns (CircuitBreakerConfig memory) 
    {
        return CircuitBreakerConfig({
            lossThreshold: lossThreshold,
            cooldownPeriod: cooldownPeriod,
            enabled: !circuitBreakerActive
        });
    }

    /**
     * @dev Check if cooldown period has elapsed
     * @return bool Whether cooldown has elapsed
     */
    function canReset() external view returns (bool) {
        return circuitBreakerActive && 
               block.timestamp >= lastTriggered + cooldownPeriod;
    }

    /**
     * @dev Get time remaining in cooldown
     * @return uint256 Seconds remaining in cooldown (0 if can reset)
     */
    function getCooldownRemaining() external view returns (uint256) {
        if (!circuitBreakerActive) return 0;
        
        uint256 elapsed = block.timestamp - lastTriggered;
        return elapsed >= cooldownPeriod ? 0 : cooldownPeriod - elapsed;
    }

    /**
     * @dev Get circuit breaker statistics
     * @return totalTriggers_ Total number of triggers
     * @return lastTriggered_ Timestamp of last trigger
     * @return isActive Whether circuit breaker is currently active
     */
    function getCircuitBreakerStats() 
        external 
        view 
        returns (
            uint256 totalTriggers_,
            uint256 lastTriggered_,
            bool isActive
        ) 
    {
        return (totalTriggers, lastTriggered, circuitBreakerActive);
    }

    /**
     * @dev Override _beforeTokenTransfer to check circuit breaker
     * This should be called by inheriting contracts
     */
    function _checkCircuitBreakerBeforeTransfer() internal view {
        require(!circuitBreakerActive, "Circuit breaker active");
    }

    /**
     * @dev Modifier to check circuit breaker status
     */
    modifier whenCircuitBreakerNotActive() {
        require(!circuitBreakerActive, "Circuit breaker active");
        _;
    }

    /**
     * @dev Modifier to check if circuit breaker can be reset
     */
    modifier canResetCircuitBreaker() {
        require(circuitBreakerActive, "Circuit breaker not active");
        require(
            block.timestamp >= lastTriggered + cooldownPeriod, 
            "Cooldown period not elapsed"
        );
        _;
    }
}
