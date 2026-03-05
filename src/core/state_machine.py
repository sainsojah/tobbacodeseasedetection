"""
User state transition management
Tracks and manages user conversation states
"""
from .constants import UserState

class StateMachine:
    """Manages user state transitions"""
    
    # Valid state transitions
    TRANSITIONS = {
        UserState.AWAITING_NAME.value: [
            UserState.ACTIVE.value,
            UserState.AWAITING_NAME.value
        ],
        UserState.ACTIVE.value: [
            UserState.WAITING_IMAGE.value,
            UserState.FEEDBACK_MODE.value,
            UserState.AWAITING_COMMENT.value,
            UserState.AWAITING_EXPERT_QUERY.value,
            UserState.CHAT_MODE.value,
            UserState.ACTIVE.value
        ],
        UserState.WAITING_IMAGE.value: [
            UserState.ANALYZING.value,
            UserState.ACTIVE.value,
            UserState.WAITING_IMAGE.value
        ],
        UserState.ANALYZING.value: [
            UserState.RESULT_SENT.value,
            UserState.ACTIVE.value
        ],
        UserState.RESULT_SENT.value: [
            UserState.ACTIVE.value,
            UserState.WAITING_IMAGE.value
        ],
        UserState.FEEDBACK_MODE.value: [
            UserState.ACTIVE.value,
            UserState.AWAITING_COMMENT.value
        ],
        UserState.AWAITING_COMMENT.value: [
            UserState.ACTIVE.value
        ],
        UserState.AWAITING_EXPERT_QUERY.value: [
            UserState.ACTIVE.value
        ],
        UserState.AWAITING_CLARIFICATION.value: [
            UserState.ACTIVE.value,
            UserState.RESULT_SENT.value
        ]
    }
    
    @classmethod
    def can_transition(cls, current_state, new_state):
        """Check if transition is valid"""
        if current_state not in cls.TRANSITIONS:
            return False
        return new_state in cls.TRANSITIONS[current_state]
    
    @classmethod
    def get_next_states(cls, current_state):
        """Get all valid next states"""
        return cls.TRANSITIONS.get(current_state, [])
    
    @classmethod
    def is_valid_state(cls, state):
        """Check if state exists"""
        return state in [s.value for s in UserState]
    
    @classmethod
    def get_initial_state(cls):
        """Get initial state for new users"""
        return UserState.AWAITING_NAME.value

# State timeout constants (in seconds)
STATE_TIMEOUTS = {
    UserState.WAITING_IMAGE.value: 300,      # 5 minutes
    UserState.AWAITING_COMMENT.value: 600,    # 10 minutes
    UserState.AWAITING_EXPERT_QUERY.value: 600, # 10 minutes
    UserState.ANALYZING.value: 120,           # 2 minutes
    UserState.AWAITING_CLARIFICATION.value: 300, # 5 minutes
}

def get_state_timeout(state):
    """Get timeout for a state"""
    return STATE_TIMEOUTS.get(state, 1800)  # Default 30 minutes