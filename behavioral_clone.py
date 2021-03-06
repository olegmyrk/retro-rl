import sys
import os
import numpy as np
import tensorflow as tf
import time

import ppo2.policies as policies
from dqn.soft_dqn_scalar import noisy_net_models
from gym import spaces

if os.environ['RETRO_CLONE'] == 'policy':
  clone_mode='policy'
elif os.environ['RETRO_CLONE'] == 'valuefun':
  clone_mode='valuefun'
elif os.environ['RETRO_CLONE'] == 'advantage':
  clone_mode='advantage'
else:
  assert False

def parse_record(record_bytes, obs_steps=4, target_count=7):
  features = {
            #'game_name' : tf.FixedLenFeature((), tf.string),
            #'act_name' : tf.FixedLenFeature((), tf.string),
            #'total_steps' : tf.FixedLenFeature((), tf.int64),
            #'episode' : tf.FixedLenFeature((), tf.int64),
            #'episode_step' : tf.FixedLenFeature((), tf.int64),
            'obs' : tf.FixedLenFeature((), tf.string),
            'action' : tf.FixedLenFeature((), tf.int64) 
          }
  if clone_mode == 'policy':
    features['action_probs'] = tf.FixedLenFeature((target_count), tf.float32)
  elif clone_mode == 'valuefun':
    features['action_values'] = tf.FixedLenFeature((target_count), tf.float32)
  elif clone_mode == 'advantage':
    features['action_probs'] = tf.FixedLenFeature((target_count), tf.float32)
  else:
    assert False
  result = tf.parse_single_example(record_bytes, features) 
  obs = tf.reshape(tf.decode_raw(result['obs'], tf.uint8), [84,84,obs_steps])
  if clone_mode == 'policy':
    return obs, result['action_probs']
  elif clone_mode == 'valuefun':
    return obs, result['action_values']
  elif clone_mode == 'advantage':
    return obs, result['action_probs']
  else:
    assert False

def build_combined_dataset(events_path):
  return tf.data.Dataset.list_files(events_path + "*.events.tfrecords").apply(tf.contrib.data.parallel_interleave(tf.data.TFRecordDataset, cycle_length=100, block_length=1)).map(parse_record, num_parallel_calls=10).shuffle(10000).repeat().batch(64).prefetch(1)

events_path = sys.argv[1]
output_path = sys.argv[2]

checkpoints_path = output_path + "tensorflow"
os.makedirs(checkpoints_path, exist_ok=True)

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
#config.log_device_placement=True
with tf.Session(config=config) as sess:
  if clone_mode == 'policy':
    model = policies.CnnPolicy(sess, np.zeros([84,84,4]), spaces.Discrete(7), 64, 4, reuse=False)
  elif clone_mode =='valuefun':
    class ShapeDummy(object):
       def __init__(self):
         self.out_shape=(84,84,4)
    model = noisy_net_models(sess, 7, ShapeDummy(), sigma0=0.0)[0]
  elif clone_mode =='advantage':
    class ShapeDummy(object):
       def __init__(self):
         self.out_shape=(84,84,4)
    model = noisy_net_models(sess, 7, ShapeDummy(), sigma0=0.0)[0]
  else:
    assert False
 
  if clone_mode == 'policy': 
    model_scope_re='^ppo2_model/'
  elif clone_mode == 'valuefun':
    model_scope_re='^dqn_model/'
  elif clone_mode == 'advantage':
    model_scope_re='^dqn_model/'
  else:
    assert False

  dataset = build_combined_dataset(events_path) 
  batch_tensor = dataset.make_one_shot_iterator().get_next()

  global_step = tf.train.create_global_step()

  if clone_mode == 'policy':
    train_obs = model.X
    train_targets = tf.placeholder(tf.float32, [None, 7])
    model_targets = model.pd.logits
    train_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(labels=train_targets, logits=model_targets))
    saver_variables = tf.trainable_variables(model_scope_re)
  elif clone_mode == 'valuefun': 
    train_obs = tf.placeholder(tf.uint8, [None, 84,84,4])
    train_targets = tf.placeholder(tf.float32, [None, 7])
    with tf.variable_scope(model.name, reuse=True):
      model_targets = model.value_func(model.base(train_obs))
    train_loss = tf.reduce_mean(tf.square(model_targets - train_targets))
    saver_variables = list(filter(lambda v: not 'sigma' in v.name, tf.trainable_variables(model_scope_re)))
  elif clone_mode == 'advantage': 
    train_obs = tf.placeholder(tf.uint8, [None, 84,84,4])
    train_targets = tf.placeholder(tf.float32, [None, 7])
    with tf.variable_scope(model.name, reuse=True):
      model_targets = model.value_func(model.base(train_obs))
    train_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(labels=train_targets, logits=model_targets))
    saver_variables = list(filter(lambda v: not 'sigma' in v.name, tf.trainable_variables(model_scope_re)))
  else:
    assert False
 
  train_step = tf.train.AdamOptimizer(learning_rate=0.0001).minimize(train_loss, global_step = global_step)

  init_op = tf.global_variables_initializer()

  #print("BEHAVIORAL_CLONE_ALL_VARIABLES: %s" % (tf.trainable_variables()))
  #saver = tf.train.Saver(var_list=tf.trainable_variables(), max_to_keep=None)
  print("BEHAVIORAL_CLONE_VARIABLES: %s" % (list(map(lambda v:v.name, saver_variables)),))
  saver = tf.train.Saver(var_list=saver_variables, max_to_keep=None)

  sess.run(init_op)

  latest_checkpoint = tf.train.latest_checkpoint(checkpoints_path)
  print("LOAD_CHECKPOINT: %s" % (latest_checkpoint,))
  if latest_checkpoint is not None:
    saver.restore(sess, latest_checkpoint)

  while True:
    (batch_obs, batch_target_values) = sess.run(batch_tensor)
    if (batch_obs.shape[0] != 64):
      continue
    train_loss_value, model_target_values, _, global_step_value = sess.run([train_loss, model_targets, train_step, global_step], feed_dict={train_obs:batch_obs, train_targets:batch_target_values})
    print("STEP: step=%s loss=%s" % (global_step_value, train_loss_value))
    print("TRAIN_TARGETS:", list(zip(list(model_target_values),list(batch_target_values))))
    #print([n.name for n in tf.get_default_graph().as_graph_def().node])
    sys.stdout.flush()
    if global_step_value % 1000 == 0:
      checkpoint_step = int(time.time())
      print("SAVE_CHECKPOINT: step=%s checkpoint_step=%s" % (global_step_value,checkpoint_step))
      saver.save(sess, checkpoints_path + "/checkpoint", global_step=checkpoint_step)

