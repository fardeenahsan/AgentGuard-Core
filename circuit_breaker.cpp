#include <iostream>
#include <string>
#include <chrono>
#include <mutex>

enum class State {
    CLOSED,
    OPEN,
    HALF_OPEN
};

class CircuitBreaker {
private:
    std::string service_name;
    State current_state;
    int failure_threshold;
    int failure_count;
    int success_count;
    std::chrono::seconds cooldown_period;
    std::chrono::time_point<std::chrono::steady_clock> last_state_change;
    std::mutex mtx;

    std::string stateToString(State s) {
        switch(s) {
            case State::CLOSED: return "CLOSED";
            case State::OPEN: return "OPEN";
            case State::HALF_OPEN: return "HALF_OPEN";
        }
        return "UNKNOWN";
    }

public:
    CircuitBreaker(std::string name, int threshold, int cooldown_secs) 
        : service_name(name), 
          current_state(State::CLOSED), 
          failure_threshold(threshold), 
          failure_count(0), 
          success_count(0),
          cooldown_period(cooldown_secs) {
        last_state_change = std::chrono::steady_clock::now();
    }

    // Check if execution is allowed
    bool allowRequest() {
        std::lock_guard<std::mutex> lock(mtx);
        
        if (current_state == State::OPEN) {
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - last_state_change).count();
            
            // Check if cooldown period has elapsed to move to HALF_OPEN
            if (elapsed >= cooldown_period.count()) {
                current_state = State::HALF_OPEN;
                std::cout << "[AegisMesh-C++] Circuit for [" << service_name << "] transitioned from OPEN to HALF_OPEN.\n";
            } else {
                std::cout << "[AegisMesh-C++] Circuit for [" << service_name << "] is OPEN. Request blocked (Fast-Fail).\n";
                return false;
            }
        }
        return true;
    }

    // Record a successful execution
    void recordSuccess() {
        std::lock_guard<std::mutex> lock(mtx);
        if (current_state == State::HALF_OPEN) {
            current_state = State::CLOSED;
            failure_count = 0;
            last_state_change = std::chrono::steady_clock::now();
            std::cout << "[AegisMesh-C++] Trial succeeded! Circuit for [" << service_name << "] reset to CLOSED.\n";
        } else if (current_state == State::CLOSED) {
            failure_count = 0; // Reset failure streak on success
        }
    }

    // Record a failed execution
    void recordFailure() {
        std::lock_guard<std::mutex> lock(mtx);
        failure_count++;
        std::cout << "[AegisMesh-C++] Failure recorded for [" << service_name << "]. Streak: " << failure_count << "\n";

        if (current_state == State::HALF_OPEN) {
            current_state = State::OPEN;
            last_state_change = std::chrono::steady_clock::now();
            std::cout << "[AegisMesh-C++] Trial failed! Circuit for [" << service_name << "] tripped back to OPEN.\n";
        } else if (current_state == State::CLOSED && failure_count >= failure_threshold) {
            current_state = State::OPEN;
            last_state_change = std::chrono::steady_clock::now();
            std::cout << "[AegisMesh-C++] Failure threshold reached! Circuit for [" << service_name << "] tripped to OPEN.\n";
        }
    }

    State getState() {
        std::lock_guard<std::mutex> lock(mtx);
        return current_state;
    }
};

extern "C" {
    // Factory functions to create and manage instances from Python
    CircuitBreaker* create_circuit_breaker(const char* name, int threshold, int cooldown_secs) {
        return new CircuitBreaker(std::string(name), threshold, cooldown_secs);
    }

    bool cb_allow_request(CircuitBreaker* cb) {
        return cb ? cb->allowRequest() : true;
    }

    void cb_record_success(CircuitBreaker* cb) {
        if (cb) cb->recordSuccess();
    }

    void cb_record_failure(CircuitBreaker* cb) {
        if (cb) cb->recordFailure();
    }

    void destroy_circuit_breaker(CircuitBreaker* cb) {
        delete cb;
    }
}