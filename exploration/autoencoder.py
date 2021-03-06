import os
import tensorflow as tf

class Autoencoder:
  def __init__(self, nfilters):
    self.nfilters = nfilters

  def observations(self):
    with tf.variable_scope("observations"):
      observations = tf.placeholder(tf.uint8, [None, 84, 84, 1])
    return observations

  def observations_rescaled(self, observations):
    with tf.variable_scope("rescaler"):
      observations_rescaled = tf.cast(observations, tf.float32) / 255.
    return observations_rescaled

  def encoder(self, inputs, embedding_activation, reuse=False):
    with tf.variable_scope("encoder", reuse=reuse):
      net = tf.layers.conv2d(inputs, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="conv1")
      net = tf.layers.conv2d(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="conv2")
      net = tf.layers.conv2d(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="conv3")
      net = tf.layers.conv2d(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="conv4")
      embeddings = tf.layers.dense(tf.reshape(net, [-1,6*6*self.nfilters]), 64, activation=embedding_activation, name="fc")
    return embeddings

  def embeddings_noisy(self, embeddings):
    with tf.variable_scope("noise"):
      embeddings_noisy = embeddings + tf.random_uniform(tf.shape(embeddings), -0.3,0.3)
    return embeddings_noisy

  def decoder(self, embeddings, reuse=False):
    with tf.variable_scope("decoder", reuse=reuse):
      net = tf.layers.dense(embeddings, 6*6*self.nfilters, activation=tf.nn.relu, name="fc")
      net = tf.reshape(net, [-1, 6, 6, self.nfilters])
      net = tf.layers.conv2d_transpose(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="deconv4")
      net = tf.layers.conv2d_transpose(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="deconv3")
      net = tf.layers.conv2d_transpose(net, self.nfilters, [6, 6], strides=2, padding='SAME', activation=tf.nn.relu, name="deconv2")                
      result = tf.layers.conv2d_transpose(net, 1, [6, 6], strides=2, padding='SAME', activation=tf.nn.sigmoid, name="deconv1")
      outputs = tf.image.resize_images(result, size=(84,84), method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
    return outputs

  def reconstruction_errors(self, observations_rescaled, outputs):
    with tf.variable_scope("reconstruction"):
      reconstruction_errors = tf.reduce_sum(tf.square(observations_rescaled - outputs),[1,2,3])
    return reconstruction_errors

  def embedding_loss_noisy(self, embeddings):
    with tf.variable_scope("embeddings"):
      embedding_loss = tf.reduce_mean(tf.reduce_mean(tf.minimum((1-embeddings)**2,embeddings**2), [1]))
    return embedding_loss

  def embedding_loss(self, embeddings):
    with tf.variable_scope("embeddings"):
      embedding_loss = tf.reduce_mean(tf.reduce_sum(embeddings**2, [1]))
    return embedding_loss

  def model(self, use_noisy=False, use_embedding_loss=False):
    model_obses = self.observations() 
    model_rescaled_obses = self.observations_rescaled(model_obses)
    model_embeddings_original = self.encoder(model_rescaled_obses, tf.nn.sigmoid if use_noisy else tf.nn.relu)
    if use_noisy:
      model_embeddings = self.embeddings_noisy(model_embeddings_original)
    else:
      model_embeddings = model_embeddings_original
    model_outputs = self.decoder(model_embeddings)

    reconstruction_errors = self.reconstruction_errors(model_rescaled_obses, model_outputs)
    reconstruction_loss = tf.reduce_mean(reconstruction_errors)
    if use_noisy:
      embedding_loss = self.embedding_loss_noisy(model_embeddings_original)
    else:
      embedding_loss = self.embedding_loss(model_embeddings_original)
    if use_embedding_loss:
      train_loss = reconstruction_loss + embedding_loss
    else:
      train_loss = reconstruction_loss
    
    return model_obses, (model_embeddings_original, model_embeddings), reconstruction_errors, (reconstruction_loss, embedding_loss), train_loss
