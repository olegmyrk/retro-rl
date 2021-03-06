import re
import sys
import os
import csv
import cloudpickle
import gzip 
import itertools
import numpy as np
import tensorflow as tf

def collect_policy_targets(root_path, game_act_name, start_step, stop_step, event_file_name, obs_steps=4):
    print("ANALYZING: %s" % (root_path + "/" + game_act_name,))
    #event_file = gzip.open(event_file_name + ".temp", "wb")
    event_writer = tf.python_io.TFRecordWriter(event_file_name + ".temp")
    game_name = '-'.join(game_act_name.split('-')[0:-1])
    act_name = game_act_name.split('-')[-1]
    obs = []
    obs_total_steps = None
    obs_episode = None
    obs_episode_step = None
    policy_total_steps = None
    policy_episode = None
    policy_episode_step = None
    policy_action_values =  None
    policy_action_probs = None
    policy_action = None
    for line in open(root_path + '/' + game_act_name + '/log', 'r'):
      key_values = dict(re.findall(r'(\S+)=(\[[^\]]*\]|{[^}]*}|[^ ]*)', line.rstrip()))
      if not 'total_steps' in key_values: continue
      total_steps = int(key_values['total_steps'])
      print("PROCESSING: game=%s act=%s total_steps=%s" % (game_name, act_name, total_steps,))
      if total_steps < start_step: continue
      if total_steps > stop_step: break
      if line.startswith("POLICY"):
        policy_total_steps = total_steps
        policy_action = int(key_values['action'])
        policy_action_values = key_values.get('action_values')
        if policy_action_values:
          policy_action_values = eval(policy_action_values)
        policy_action_probs = eval(key_values['action_probs'])
      elif line.startswith("STEP:"):
        episode = int(key_values['episode'])
        episode_step = int(key_values['episode_step'])
        action = int(key_values['action'])
        if obs_total_steps == total_steps-1 and obs_episode == episode and policy_total_steps == total_steps:
          assert obs_episode_step == episode_step - 1
          assert policy_action == action
          assert len(obs) == obs_steps
          obs_arr = np.dstack(obs)
          print("EVENT: game=%s act=%s total_steps=%s episode=%s episode_step=%s obs=%s action_values=%s action_probs=%s action=%s" % (game_name, act_name, total_steps, episode, episode_step, obs_arr.shape, policy_action_values, policy_action_probs, policy_action))
          #event = { 'game_name' : game_name, 'act_name' : act_name, 'total_steps' : total_steps, 'episode' : episode, 'episode_step' : episode_step, 'obs' : obs_arr, 'action_values' : policy_action_values, 'action_probs' : policy_action_probs, 'action' : policy_action }
          features = {
            'game_name' : tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(game_name)])),
            'act_name' : tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(act_name)])),
            'total_steps' : tf.train.Feature(int64_list=tf.train.Int64List(value=[total_steps])), 
            'episode' : tf.train.Feature(int64_list=tf.train.Int64List(value=[episode])), 
            'episode_step' : tf.train.Feature(int64_list=tf.train.Int64List(value=[episode_step])),
            'obs' : tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(obs_arr.tostring())])),
            'obs_shape' : tf.train.Feature(int64_list=tf.train.Int64List(value=obs_arr.shape)),
            'action_probs' : tf.train.Feature(float_list=tf.train.FloatList(value=policy_action_probs)),
            'action' : tf.train.Feature(int64_list=tf.train.Int64List(value=[policy_action])) 
          }
          if policy_action_values:
            features['action_values'] =  tf.train.Feature(float_list=tf.train.FloatList(value=policy_action_values))
          record = tf.train.Example(features=tf.train.Features(feature=features))
          #cloudpickle.dump(event, event_file)
          event_writer.write(record.SerializeToString())
        step_data = cloudpickle.load(gzip.open(root_path + '/' + game_act_name + '/' + game_act_name + "-" + str(episode).zfill(4) + ".steps/" + str(episode) + "." + str(episode_step) + ".step.gz", 'rb'))
        assert int(step_data['total_steps']) == total_steps
        assert int(step_data['episode']) == episode
        assert int(step_data['episode_step']) == episode_step
        assert int(step_data['action']) == action
        obs_total_steps = total_steps
        obs_episode = episode
        obs_episode_step = episode_step
        obs_new = step_data['obs']
        if not hasattr(obs_new, 'shape'):
          obs_new = obs_new.__array__()
        if len(obs_new.shape) == 3:
          obs = [obs_new[:,:,i] for i in range(0,obs_new.shape[2])] 
        else:
          obs.append(obs_new)
        if len(obs) > obs_steps:
          obs = obs[-obs_steps:]
        elif len(obs) < obs_steps:
          obs_zeros = np.zeros_like(obs[-1], dtype=np.uint8)
          obs = list(itertools.repeat(obs_zeros, obs_steps - len(obs))) + obs 
    #event_file.close()
    event_writer.close()
    os.rename(event_file_name + ".temp", event_file_name)

root_path, game_act_name, start_step, stop_step, event_path = (sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])

#event_file_name = event_path + "/" + game_act_name + ".events.gz"
event_file_name = event_path + "/" + game_act_name + ".events.tfrecords"
if not os.path.exists(event_file_name):
  collect_policy_targets(root_path, game_act_name, start_step, stop_step, event_file_name)
else:
  print("SKIPPING: game_act_name=%s" % (game_act_name,))
