"""
This script contains code for a Convolutional Neural Network
that classifies a 10-second audio clip into one of five 
laughter categories: baby laughter, belly laugh, chuckle/chortle, 
giggle, snicker.

Author: Ganesh Srinivas <gs401 [at] snu.edu.in>
"""

import glob
import os
import random
import subprocess

import tensorflow as tf
import numpy as np

#import feature_extraction
import librosa

## Dataset location
FILENAMES = "../../laughter_files.txt"
DATASET_LOCATION = ""

## Hyperparameters
# for Learning algorithm
learning_rate = 0.0001
batch_size = 120 
training_iterations = 1950

# for Feature extraction
max_audio_length = 221184
frames = 433
bands = 60
feature_size = frames*bands #433x60

# for Network
num_labels = 2
num_channels = 2

kernel_size = 30
depth = 20
num_hidden = 200

## Helper functions for loading data and extracting features
def labeltext2labelid(category_name):
    """
    Returns a numerical label for each laughter category
    """
    #possible_categories = ['baby_laughter_clips', 'belly_laugh_clips', \
    #'chuckle_chortle_clips', 'giggle_clips', 'nota_clips', 'snicker_clips']
    #possible_categories = ['laughter', 'speech']
    #print("category_name: " + category_name)

    if category_name == "samples":
        return 0
    else:
        return 1

    #return possible_categories.index(category_name)

def shape_sound_clip(sound_clip, required_length=max_audio_length):
    """
    Shapes sound clips to have constant length
    """
    difference = required_length-sound_clip.shape[0]
    if difference == 0:
        return sound_clip
    elif difference < 0:
        # Clip length exceeds required length. Trim it.
        modified_sound_clip = sound_clip[:-difference]
        return modified_sound_clip
    else:
        z = np.zeros((required_length - sound_clip.shape[0],))
        modified_sound_clip = np.append(sound_clip, z)
        return modified_sound_clip

def extract_labels(filenames):
    labels = []

    for f in filenames:
        labels.append(labeltext2labelid(f.split('/')[-2]))

    return labels

def extract_features(filenames):
    print("Number of files:" + str(len(filenames)))
    """
    Extract log-scaled mel-spectrograms and their corresponding
    deltas from the sound clips
    """
    log_specgrams = []
    for f in filenames:
        #print(f)
        signal, s = librosa.load(f)
        sound_clip = shape_sound_clip(signal)

        melspec = librosa.feature.melspectrogram(sound_clip, n_mels=60)
        #print melspec.shape

        logspec = librosa.power_to_db(melspec, ref=np.max)
        #print logspec.shape
        logspec = logspec.T.flatten()[:, np.newaxis].T
        #print logspec.shape

        #print "Produce of two elements in melspec: ", melspec.shape[0]*melspec.shape[1]
        log_specgrams.append(logspec)
        del signal
        del sound_clip
        del melspec
        del logspec

    log_specgrams = np.asarray(log_specgrams).reshape(len(log_specgrams), bands, frames, 1)

    features = np.concatenate((log_specgrams, np.zeros(np.shape(log_specgrams))), axis=3)

    for i in range(len(features)):
        features[i, :, :, 1] = librosa.feature.delta(features[i, :, :, 0])

    return np.array(features)

def one_hot_encode(labels, num_labels=num_labels):
    """
    Convert list of label IDs to a list of one-hot encoding vectors
    """
    n_labels = len(labels)
    n_unique_labels = num_labels

    one_hot_encode = np.zeros((n_labels, n_unique_labels))
    one_hot_encode[np.arange(n_labels), labels] = 1

    return one_hot_encode

## Helper functions for defining the network
def weight_variable(shape):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial)

def bias_variable(shape):
    initial = tf.constant(1.0, shape=shape)
    return tf.Variable(initial)

def conv2d(x, W):
    return tf.nn.conv2d(x, W, strides=[1, 2, 2, 1], padding='SAME')

def apply_convolution(x, kernel_size, num_channels, depth):
    weights = weight_variable([kernel_size, kernel_size, num_channels, depth])
    biases = bias_variable([depth])

    return tf.nn.relu(tf.add(conv2d(x, weights), biases))

def apply_max_pool(x, kernel_size, stride_size):
    return tf.nn.max_pool(x, ksize=[1, kernel_size, kernel_size, 1],
                          strides=[1, stride_size, stride_size, 1], padding='SAME')

## Defining the network as a TensorFlow computational graph
X = tf.placeholder(tf.float32, shape=[None, bands, frames, num_channels])
Y = tf.placeholder(tf.float32, shape=[None, num_labels])

# normalization
X_normalized = tf.nn.l2_normalize(X, dim=0)

cov = apply_convolution(X_normalized, kernel_size, num_channels, depth)
shape = cov.get_shape().as_list()
cov_flat = tf.reshape(cov, [-1, shape[1] * shape[2] * shape[3]])

f_weights = weight_variable([shape[1] * shape[2] * depth, num_hidden])
f_biases = bias_variable([num_hidden])

f = tf.nn.sigmoid(tf.add(tf.matmul(cov_flat, f_weights), f_biases))

out_weights = weight_variable([num_hidden, num_labels])
out_biases = bias_variable([num_labels])

pred = tf.nn.softmax(tf.matmul(f, out_weights) + out_biases)

# Defining the loss function
cross_entropy = -tf.reduce_sum(Y * tf.log(pred))
optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(cross_entropy)

#train_prediction = tf.nn.softmax(cross_entropy)
correct_prediction = tf.equal(tf.argmax(pred, 1), tf.argmax(Y, 1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))


def train():
    ## Loading the test and train clips.
    with open(FILENAMES, "r") as fh:
        filecontents = fh.read()
        filenames = filecontents.split('\n')
        filenames = filenames[:-1]
        filenames = [DATASET_LOCATION+f for f in filenames]

    random.seed(10)
    random.shuffle(filenames)
    rnd_indices = np.random.rand(len(filenames)) < 0.80

    print(len(rnd_indices))
    train = []
    test = []

    for i in range(len(filenames)):
        random.seed()
        if random.random() < .95:
            train.append(filenames[i])
        else:
            test.append(filenames[i])

    train_x, train_y = extract_features(train), extract_labels(train)
    test_x, test_y = extract_features(test), extract_labels(test)
    test_y = one_hot_encode(test_y)

    ## Running the computational graph
    # We run the training algorithm in batches and compute the loss
    # for each batch, and optimize the network weights accordingly.
    # In the end, we look at the accuracy of the trained network on the
    # test set.
    cost_history = np.empty(shape=[1], dtype=float)
    saver = tf.train.Saver(max_to_keep=5, keep_checkpoint_every_n_hours=1)
    with tf.Session() as session:
        tf.initialize_all_variables().run()
        for itr in range(training_iterations):
            offset = (itr * batch_size) % (len(train) - batch_size)
            batch_x = train_x[offset:(offset + batch_size)]
            batch_y = train_y[offset:(offset + batch_size)]
            batch_y = one_hot_encode(batch_y)
            if itr % 10 == 0:
                print('Test Accuracy: {}'.format(session.run(accuracy, feed_dict={X: test_x, Y: test_y})))
                saver.save(session, "./model", global_step=itr)
            _, c, a = session.run([optimizer, cross_entropy, accuracy], feed_dict={X: batch_x, Y: batch_y})
            print(_)
            print(c)
            print(a)
            print("Training iteration {}: accuracy {}".format(itr, a))
            cost_history = np.append(cost_history, c)
            del batch_x

        print('Final accuracy: {}'.format(session.run(accuracy, feed_dict={X: test_x, Y: test_y})))

        session.run(accuracy, feed_dict={X: test_x, Y: test_y})
        #fig = plt.figure(figsize=(15,10))

        #plt.plot(cost_history)
        #plt.axis([0,training_iterations,0,np.max(cost_history)])
        #plt.show()

def apply():
    def toText(value):
        if value == 0:
            return "laughter"
        else:
            return "-"

    import os

    def files():
        for dirname, dirnames, filenames in os.walk('G:\\video\\1sec\\D9Ihs241zeg\\'):
            for f in filenames:
                if (f.endswith(".wav")):
                    yield os.path.join(dirname, f)

    filenames = [f for f in files()]

    # https://stackoverflow.com/questions/33759623/tensorflow-how-to-save-restore-a-model
    print("applying...")

    session = tf.Session()
    #First let's load meta graph and restore weights
    saver = tf.train.import_meta_graph('./model-210.meta')
    saver.restore(session, tf.train.latest_checkpoint('./'))
    tf.initialize_all_variables().run(session=session)

    test_x = extract_features(filenames)

    # accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
    # correct_prediction = tf.equal(tf.argmax(pred,1), tf.argmax(Y,1))
    predictions = session.run(tf.argmax(pred, 1), feed_dict={X: test_x})
    [print(p) for p in predictions]

    files = [f.split('\\')[-1].split(".")[0] for f in filenames]
    predictions = zip(files, [toText(l) for l in predictions])
    
    [print(p) for p in predictions]


apply()