'''
Example of a single-layer bidirectional long short-term memory network trained with
connectionist temporal classification to predict phoneme sequences from nFeatures x nFrames
arrays of Mel-Frequency Cepstral Coefficients.  This is basically a recreation of an experiment
on the TIMIT data set from chapter 7 of Alex Graves's book (Graves, Alex. Supervised Sequence 
Labelling with Recurrent Neural Networks, volume 385 of Studies in Computational Intelligence.
Springer, 2012.), minus the early stopping.

Author: Jon Rein
'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
from tensorflow.python.ops import ctc_ops as ctc
from tensorflow.python.ops import rnn_cell
from tensorflow.python.ops.rnn import bidirectional_rnn
import numpy as np
from ctc_example.utils import load_batched_data
from lstm_siamese import dir_dictionary
import os.path

trainset_numpy_feature = os.path.join(dir_dictionary['features'], 'TIMIT_train', 'feature')
trainset_numpy_label = os.path.join(dir_dictionary['features'], 'TIMIT_train', 'label')
INPUT_PATH = trainset_numpy_feature
TARGET_PATH = trainset_numpy_label

####Learning Parameters
learningRate = 0.001
momentum = 0.9
nEpochs = 120
batchSize = 10

####Network Parameters
nFeatures = 26 #12 MFCC coefficients + energy, and derivatives
nHidden = 128
nClasses = 62 #39 phonemes, plus the "blank" for CTC

####Load data
print('Loading data')
batchedData, maxTimeSteps, totalN = load_batched_data(INPUT_PATH, TARGET_PATH, batchSize)
print('maxTimeSteps', maxTimeSteps, 'totalN', totalN)

def LSTM_Network(input_, weightsOutH1, weightsClasses, biasesOutH1, biasesClasses):
    ####Network
    forwardH1 = rnn_cell.LSTMCell(nHidden, use_peepholes=True, state_is_tuple=True)
    backwardH1 = rnn_cell.LSTMCell(nHidden, use_peepholes=True, state_is_tuple=True)
    fbH1, _, _ = bidirectional_rnn(forwardH1, backwardH1, inputList, dtype=tf.float32,
        scope='BDLSTM_H1')
    fbH1rs = [tf.reshape(t, [batchSize, 2, nHidden]) for t in fbH1]
    outH1 = [tf.reduce_sum(tf.mul(t, weightsOutH1), reduction_indices=1) + biasesOutH1 for t in fbH1rs]

    logits = [tf.matmul(t, weightsClasses) + biasesClasses for t in outH1]

    ####Optimizing
    logits3d = tf.pack(logits)
    return logits3d


####Define graph
print('Defining graph')
graph = tf.Graph()
with graph.as_default():

    ####NOTE: this work is unfinished. 
        
    ####Graph input
    inputL = tf.placeholder(tf.float32, shape=(maxTimeSteps, batchSize, nFeatures))
    #Prep input data to fit requirements of rnn.bidirectional_rnn
    #  Reshape to 2-D tensor (nTimeSteps*batchSize, nfeatures)
    xL = tf.reshape(inputL, [-1, nFeatures])
    # Split to get a list of 'n_steps' tensors of shape (batch_size, n_input)
    xL = tf.split(0, maxTimeSteps, xL)
    ####Graph input
    inputR = tf.placeholder(tf.float32, shape=(maxTimeSteps, batchSize, nFeatures))
    #Prep input data to fit requirements of rnn.bidirectional_rnn
    #  Reshape to 2-D tensor (nTimeSteps*batchSize, nfeatures)
    xR = tf.reshape(inputR, [-1, nFeatures])
    # Split to get a list of 'n_steps' tensors of shape (batch_size, n_input)
    xR = tf.split(0, maxTimeSteps, xR)
     
    label = tf.placeholder(tf.float32, [None])
    
    ####Weights & biases
    weightsOutH1 = tf.Variable(tf.truncated_normal([2, nHidden],
        stddev=np.sqrt(2.0 / (2*nHidden))))
    biasesOutH1 = tf.Variable(tf.zeros([nHidden]))
    weightsClasses = tf.Variable(tf.truncated_normal([nHidden, nClasses],
      stddev=np.sqrt(2.0 / nHidden)))
    biasesClasses = tf.Variable(tf.zeros([nClasses]))

    with tf.variable_scope("RNN") as scope:
        o1 = LSTM_Network(xL, weightsOutH1, weightsClasses, biasesOutH1, biasesClasses)
        scope.reuse_variables()
        o2 = LSTM_Network(xR, weightsOutH1, weightsClasses, biasesOutH1, biasesClasses)

    loss = tf.reduce_mean(ctc.ctc_loss(logits3d, targetY, seqLengths))
    optimizer = tf.train.MomentumOptimizer(learningRate, momentum).minimize(loss)



saver = tf.train.Saver()

####Run session
with tf.Session(graph=graph) as session:
    print('Initializing')
    #tf.initialize_all_variables().run()
    saver.restore(sess, "/tmp/model.ckpt")
    for epoch in range(nEpochs):
        print('Epoch', epoch+1, '...')
        batchErrors = np.zeros(len(batchedData))
        batchRandIxs = np.random.permutation(len(batchedData)) #randomize batch order
        for batch, batchOrigI in enumerate(batchRandIxs):
            batchInputs, batchTargetSparse, batchSeqLengths = batchedData[batchOrigI]
            batchTargetIxs, batchTargetVals, batchTargetShape = batchTargetSparse
            feedDict = {inputX: batchInputs, targetIxs: batchTargetIxs, targetVals: batchTargetVals,
                        targetShape: batchTargetShape, seqLengths: batchSeqLengths}
            _, l, er, lmt = session.run([optimizer, loss, errorRate, logitsMaxTest], feed_dict=feedDict)
            print(np.unique(lmt)) #print unique argmax values of first sample in batch; should be blank for a while, then spit out target values
            if (batch % 1) == 0:
                print('Minibatch', batch, '/', batchOrigI, 'loss:', l)
                print('Minibatch', batch, '/', batchOrigI, 'error rate:', er)
            batchErrors[batch] = er*len(batchSeqLengths)
        epochErrorRate = batchErrors.sum() / totalN
        print('Epoch', epoch+1, 'error rate:', epochErrorRate)
