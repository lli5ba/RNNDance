# -*- coding: utf-8 -*-
"""
Created on Tue Mar 22 10:43:29 2016

@author: Rob Romijnders

TODO
- Cross validate over different learning-rates
"""
import random
import sys
sys.path.append('/home/rob/Dropbox/ml_projects/basket_local')
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from tensorflow.python.framework import ops
from tensorflow.python.ops import clip_ops
from util_basket import *
from util_MDN import *
from dataloader import *
from mpl_toolkits.mplot3d import axes3d
import matplotlib.mlab as mlab


class Model():
  def __init__(self,config):
    """Hyperparameters"""
    num_layers = config['num_layers']
    hidden_size = config['hidden_size']
    max_grad_norm = config['max_grad_norm']
    batch_size = config['batch_size']
    sl = config['sl']
    mixtures = config['mixtures']
    crd = config['crd']
    learning_rate = config['learning_rate']
    MDN = config['MDN']
    self.sl = sl #tsteps = sequence length
    self.crd = crd
    self.batch_size = batch_size
    self.pjoints = 20




    # Nodes for the input variables
    self.x = tf.placeholder("float", shape=[batch_size, crd,sl], name = 'Input_data')
    self.y_ = tf.placeholder(tf.int64, shape=[batch_size], name = 'Ground_truth')
    self.keep_prob = tf.placeholder("float")
    with tf.name_scope("LSTM") as scope:
      cell = tf.contrib.rnn.LSTMCell(hidden_size,use_peepholes = True)
      cell = tf.contrib.rnn.MultiRNNCell([cell] * num_layers)
      cell = tf.contrib.rnn.DropoutWrapper(cell,output_keep_prob=self.keep_prob)

      #Initial state
      initial_state = cell.zero_state(batch_size, tf.float32)


      outputs = []
      self.states = []
      state = initial_state
      for time_step in range(sl):
        if time_step > 0: tf.get_variable_scope().reuse_variables()
        (cell_output, state) = cell(self.x[:, :, time_step], state)
        outputs.append(cell_output)
        self.states.append(state)
      self.final_state = state
      #outputs is now a list of length seq_len with tensors [ batch_size by hidden_size ]
    with tf.name_scope("SoftMax") as scope:
      final = outputs[-1]
      W_c = tf.Variable(tf.random_normal([hidden_size,2], stddev=0.01))
      b_c = tf.Variable(tf.constant(0.1, shape=[2]))
      self.h_c = tf.matmul(final, W_c) + b_c

      loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=self.h_c,labels=self.y_)
      self.cost = tf.reduce_mean(loss)
      loss_summ = tf.summary.scalar("cross entropy_loss", self.cost)
    with tf.name_scope("Output_MDN") as scope:
      params = 8 #7+theta  (should be 20*8?)
      output_units = mixtures*params *20 #Two for distribution over hit&miss, params for distribution parameters
      W_o = tf.Variable(tf.random_normal([hidden_size,output_units], stddev=0.01))
      b_o = tf.Variable(tf.constant(0.5, shape=[output_units]))
      #For comparison with XYZ, only up to last time_step
      # --> because for final time_step you cannot make a prediction
      outputs_tensor = tf.concat(outputs[:-1], 0)
      h_out_tensor = tf.nn.xw_plus_b(outputs_tensor,W_o,b_o)    #is of size [batch_size*seq_len by output_units]

    with tf.name_scope('MDN_over_next_vector') as scope:
      #Next two lines are rather ugly, But its the most efficient way to reshape the data
      print(h_out_tensor)
      h_xyz = tf.reshape(h_out_tensor,(sl-1,batch_size,output_units))
      print(h_xyz)
      h_xyz = tf.transpose(h_xyz,[1,2,0])  #transpose to [batch_size, output_units, sl-1]
      print(h_xyz)
      #x_next = tf.slice(x,[0,0,1],[batch_size,3,sl-1])  #in size [batch_size, output_units, sl-1]
      x_next = tf.subtract(self.x[:,:3,1:],  self.x[:,:3,:sl-1])
      print(x_next)
      #From here any, many variables have size [batch_size, mixtures, sl-1]
      xn1,xn2,xn3 = tf.split(x_next,3,1) #tf.split(1,3,x_next)
      print(xn1)
      self.mu1,self.mu2,self.mu3,self.s1,self.s2,self.s3,self.rho,self.theta = tf.split(h_xyz,params,1)
      print(self.mu1)
      print(self.mu2)
      print(self.mu3)
      print(self.s1)
      print(self.s2)
      print(self.s3)
      print(self.rho)
      print(self.theta)
      #make the theta mixtures
      # softmax all the theta's:
      max_theta = tf.reduce_max(self.theta, 1, keep_dims=True)
      self.theta = tf.subtract(self.theta, max_theta)
      self.theta = tf.exp(self.theta)
      normalize_theta = tf.reciprocal(tf.reduce_sum(self.theta, 1, keep_dims=True))
      self.theta = tf.multiply(normalize_theta, self.theta)

      #Deviances are non-negative and tho between -1 and 1
      self.s1 = tf.exp(self.s1)
      self.s2 = tf.exp(self.s2)
      self.s3 = tf.exp(self.s3)
      self.rho = tf.tanh(self.rho)

      px1x2 = tf_2d_normal(xn1, xn2, self.mu1, self.mu2, self.s1, self.s2, self.rho)   #probability in x1x2 plane
      px3 = tf_1d_normal(xn3,self.mu3,self.s3)
      px1x2x3 = tf.multiply(px1x2,px3)

      px1x2x3_mixed = tf.reduce_sum(tf.multiply(px1x2x3,self.theta),1)  #Sum along the mixtures in dimension 1
      print('You are using %.0f mixtures'%mixtures)
      loss_seq = -tf.log(tf.maximum(px1x2x3_mixed, 1e-20)) # at the beginning, some errors are exactly zero.
      self.cost_seq = tf.reduce_mean(loss_seq)
      self.cost = self.cost_seq
      self.cost_comb = self.cost_seq
      if MDN: self.cost_comb = self.cost_seq  #The magic line where both heads come together.

    with tf.name_scope("train") as scope:
      tvars = tf.trainable_variables()
      #We clip the gradients to prevent explosion
      grads = tf.gradients(self.cost_comb, tvars)
      grads, _ = tf.clip_by_global_norm(grads,0.5)

      #Some decay on the learning rate
      global_step = tf.Variable(0,trainable=False)
      lr = tf.train.exponential_decay(learning_rate,global_step,14000,0.95,staircase=True)
      #optimizer = tf.train.AdamOptimizer(lr)
      optimizer = tf.train.GradientDescentOptimizer(lr)
      gradients = zip(grads, tvars)
      self.train_step = optimizer.apply_gradients(gradients,global_step=global_step)
      # The following block plots for every trainable variable
      #  - Histogram of the entries of the Tensor
      #  - Histogram of the gradient over the Tensor
      #  - Histogram of the grradient-norm over the Tensor
      self.numel = tf.constant([[0]])
      for gradient, variable in gradients:
        if isinstance(gradient, ops.IndexedSlices):
          grad_values = gradient.values
        else:
          grad_values = gradient

        self.numel +=tf.reduce_sum(tf.size(variable))
#
#        h1 = tf.histogram_summary(variable.name, variable)
#        h2 = tf.histogram_summary(variable.name + "/gradients", grad_values)
#        h3 = tf.histogram_summary(variable.name + "/gradient_norm", clip_ops.global_norm([grad_values]))

    with tf.name_scope("Evaluating_accuracy") as scope:
      correct_prediction = 0
      self.accuracy = tf.reduce_mean(tf.cast(correct_prediction, "float"))
      accuracy_summary = tf.summary.scalar("accuracy", self.accuracy)


    #Define one op to call all summaries
    self.merged = tf.summary.merge_all()

  def sample(self,sess,seq,sl_pre = 4,bias=0):
    """Continually samples from the MDN. The frist "sl_pre" samples
    are taken from original data in seq
    input
    - sess: tf session
    - seq: a sequence in [crd,sl]
    - sl_pre: how many predefined sequence stamps to use?"""
    assert seq.shape[1] == self.sl and seq.shape[0] == self.crd, 'Feed a sequence in [crd,sl]'
    assert sl_pre > 1, 'Please provide two predefined coordinates'

    def sample_theta(thetas):
        original = False
        if original:
          stop = np.random.rand()  #random number to stop
          num_thetas = len(thetas)
          cum = 0.0  #cumulative probability
          for i in range(num_thetas):
            cum += thetas[i]
            if cum > stop:
              return i
          print('No theta is drawn, ERROR')
          return
        else:
            return random.randint(0, 2)




    #Work around for tensor sizes, feed a tensor with zeros
    seq_feed = np.zeros((self.batch_size,self.crd,self.sl))
    seq_feed[0,:,:] = seq[:,:]
    offset_draw = np.zeros((3)) #3 coordinates
    for sl_draw in range(sl_pre,self.sl-1):  #from the predefined sequences till end
      feed_dict={ self.x: seq_feed, self.keep_prob: 1.0}
      result = sess.run([self.mu1,self.mu2,self.mu3,self.s1,self.s2,self.s3,self.rho,self.theta],feed_dict = feed_dict)
      for i in range(self.pjoints): # repeat process for each joint
        start_idx = 3*i
        end_idx = 3*i + 3
        #Sample from theta
        idx_theta = sample_theta(result[7][0,start_idx:end_idx,sl_pre])
        idx_theta = start_idx + idx_theta #account for offset of starting index
        #Collect two distributions to draw from
        #  One for XY plane
        #  One for Z plane
        mean = np.zeros((3))
        mean[0] = result[0][0,idx_theta,sl_draw]
        mean[1] = result[1][0,idx_theta,sl_draw]
        mean[2] = result[2][0,idx_theta,sl_draw]
        cov = np.zeros((3,3))
        sigma1 = np.exp(-1*bias)*result[3][0,idx_theta,sl_draw]
        sigma2 = np.exp(-1*bias)*result[4][0,idx_theta,sl_draw]
        sigma3 = np.exp(-1*bias)*result[5][0,idx_theta,sl_draw]
        sigma12 = result[6][0,idx_theta,sl_draw]*sigma1*sigma2
        cov[0,0] = np.square(sigma1)
        cov[1,1] = np.square(sigma2)
        cov[2,2] = np.square(sigma3)
        cov[1,2] = sigma12
        cov[2,1] = sigma12
        rv = multivariate_normal(mean,cov)
        draw = rv.rvs()
        offset_draw = draw
        seq_feed[0,start_idx:end_idx,sl_draw+1] = seq_feed[0,start_idx:end_idx,sl_draw]+offset_draw

    #Now draw some trajectories
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    ax.plot(seq[0,:], seq[1,:], seq[2,:],'r')
    ax.plot(seq_feed[0,0,:], seq_feed[0,1,:], seq_feed[0,2,:],'b')
    ax.set_xlabel('x coordinate')
    ax.set_ylabel('y coordinate')
    ax.set_zlabel('z coordinate')
    return seq_feed[0]
