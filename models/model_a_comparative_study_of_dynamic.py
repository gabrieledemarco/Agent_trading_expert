"""Reinforcement Learning model - model_a_comparative_study_of_dynamic."""

import torch
import torch.nn as nn
import numpy as np
from collections import deque
import random


class TradingEnvironment:
    """Trading environment for RL agent."""
    
    def __init__(self, data: np.ndarray, initial_balance: float = 10000):
        self.data = data
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0
        self.current_step = 0
        self.transaction_cost = 0.001
        
    def reset(self):
        self.balance = self.initial_balance
        self.position = 0
        self.current_step = 0
        return self._get_state()
    
    def _get_state(self):
        return np.array([
            self.balance / self.initial_balance,
            self.position / 100,  # Max position
            self.data[self.current_step] / np.max(self.data),
        ])
    
    def step(self, action: int):
        # Actions: 0 = hold, 1 = buy, 2 = sell
        price = self.data[self.current_step]
        
        if action == 1 and self.balance >= price:
            self.balance -= price
            self.position += 1
        elif action == 2 and self.position > 0:
            self.balance += price
            self.position -= 1
        
        self.current_step += 1
        done = self.current_step >= len(self.data) - 1
        
        reward = self.balance + self.position * price - self.initial_balance
        return self._get_state(), reward, done


class DQNAgent(nn.Module):
    def __init__(self, state_size: int, action_size: int, hidden_size: int = 128):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, action_size),
        )
    
    def forward(self, x):
        return self.fc(x)


class RLTrader:
    def __init__(self, state_size: int, action_size: int):
        self.agent = DQNAgent(state_size, action_size)
        self.replay_buffer = deque(maxlen=10000)
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        
    def act(self, state, epsilon=None):
        if epsilon is None:
            epsilon = self.epsilon
        if np.random.random() < epsilon:
            return np.random.randint(0, 3)
        with torch.no_grad():
            return self.agent(torch.FloatTensor(state)).argmax().item()
    
    def replay(self, batch_size: int = 32):
        if len(self.replay_buffer) < batch_size:
            return
        
        batch = random.sample(self.replay_buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        states = torch.FloatTensor(states)
        next_states = torch.FloatTensor(next_states)
        rewards = torch.FloatTensor(rewards)
        actions = torch.LongTensor(actions)
        dones = torch.FloatTensor(dones)
        
        current_q = self.agent(states).gather(1, actions.unsqueeze(1)).squeeze()
        next_q = self.agent(next_states).max(1)[0]
        target_q = rewards + (1 - dones) * self.gamma * next_q
        
        loss = nn.MSELoss()(current_q, target_q)
        
        optimizer = torch.optim.Adam(self.agent.parameters())
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay


if __name__ == "__main__":
    # Quick test
    data = np.random.randn(100).cumsum() + 100
    env = TradingEnvironment(data)
    agent = RLTrader(state_size=3, action_size=3)
    print(f"RL Agent initialized with {sum(p.numel() for p in agent.agent.parameters())} parameters")
