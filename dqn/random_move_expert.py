import numpy as np
import random

class RandomMoveExpert:
  def __init__(self):
    self.states = {}

  def configure(self, num_actions):
    self.num_actions = num_actions

  def initialize(self):
    pass

  def reset(self, env_idx):
    self.states[env_idx] = [0,0]

  def step(self, observations):
    result = []
    for env_idx in range(0,len(observations)):
      [move_steps, jump_steps] = self.states[env_idx]
      action_probs = np.asarray([0.0 for _ in range(0, self.num_actions)])
      while move_steps == 0:
        move_steps = int(1000 * (random.random() - 0.5))
        jump_steps = 0
      if jump_steps == 0 and random.random() > 0.90:
        jump_steps = random.choice(range(0,10))
      if jump_steps > 0:
        jump_steps -= 1
        action_probs[6] = 1.0
      elif move_steps > 0:
        move_steps -= 1
        action_probs[1] = 1.0
      elif move_steps < 0:
        move_steps += 1
        action_probs[0] = 1.0
      result.append(action_probs)
      self.states[env_idx] = [move_steps, jump_steps]
    return result
