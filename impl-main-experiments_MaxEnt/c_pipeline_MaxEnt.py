#!/usr/bin/env python
"""
MaxEnt Pipeline configuration:

 -> Predicting Appraisals from Text
 -> Predicting Emotions based on predicted appraisals

"""

import argparse
import sys
parser = argparse.ArgumentParser()
parser._action_groups.pop()
required = parser.add_argument_group('required arguments')
optional = parser.add_argument_group('optional arguments')
required.add_argument('--dataset', '-d',
            type=str,
            help='specify a dataset',
            choices=['enISEAR_V1', 'enISEAR_V2', 'enISEAR_V3'],
            required=True)
optional.add_argument('--folds', '-f',
            default=10, type=int,
            help='set the number of folds (default 10)')
optional.add_argument('--runs', '-r',
            default=10, type=int,
            help='set the number of runs (default 10)')
optional.add_argument('--quiet',
            action='store_true', help='reduce keras outputs')

args = parser.parse_args()
MODEL = 'MaxEnt'
_DATASET = args.dataset
KFOLDS = args.folds
ROUNDS = args.runs

if (args.quiet):
    VERBOSITY = 0
else: VERBOSITY = 1

if (_DATASET == 'enISEAR_V1'):
    DATASET = '../corpora/enISEAR-appraisal-V1/enISEAR_appraisal_majority.tsv'
    DIMENSIONS = ['Attention', 'Certainty', 'Effort', 'Pleasant', 'Responsibility', 'Control', 'Circumstance']
elif (_DATASET == 'enISEAR_V2'):
    DIMENSIONS = ['Attention', 'Certainty', 'Effort', 'Pleasant', 'Responsibility', 'Control', 'Circumstance']
    print('\nError: V2 dataset (annotations with visible emotions) not done yet.')
    print('Exiting')
    sys.exit()
    DATASET = '../corpora/enISEAR-appraisal-V2/enISEAR_appraisal.tsv'
elif (_DATASET == 'enISEAR_V3'):
    DATASET = '../corpora/enISEAR-appraisal-V3/enISEAR_appraisal_automated_binary.tsv'
    DIMENSIONS = ['Attention', 'Certainty', 'Effort', 'Pleasant', 'Resp./Control', 'Sit. Control']


print('----------------------------------')
print('   Starting pipeline experiment   ')
print('----------------------------------')
print('   Model:    \t' , MODEL)
print('   Dataset:  \t' , _DATASET)
print('   Folds:    \t', KFOLDS)
print('   Runs:     \t', ROUNDS)
print('----------------------------------\n')

import pandas as pd
import csv
import seaborn as sns
import numpy as np
import tensorflow as tf
import statistics
import datetime

from sklearn.model_selection import KFold
from sklearn.feature_extraction.text import CountVectorizer

from keras.models import Sequential
from keras.layers import Dense, Activation, Input
from keras import regularizers
from keras.initializers import Constant

import sys
sys.path.append('..')
import util.metrics as metrics


# Hide tensorflow infos
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '4'

LABELS = ['Anger', 'Disgust', 'Fear', 'Guilt', 'Joy', 'Sadness', 'Shame']
DIMENSIONS = ['Attention', 'Certainty', 'Effort', 'Pleasant', 'Responsibility', 'Control', 'Circumstance']

# Parameters
EPOCHS_AE = 25
EPOCHS_TA = 10
BATCH_SIZE = 1
OPTIMIZER = 'adam'

EXPERIMENTNAME = 'MaxEnt Pipeline 16.01.20'
SAVEFILE = 'results_pipelineMaxEnt.txt'
DATASET = '../corpora/enISEAR-appraisal-V1/enISEAR_appraisal_majority.tsv'

vectors = []
with open(DATASET) as tsvfile:
  reader = csv.reader(tsvfile, delimiter='\t')
  firstLine = True
  for row in reader:
    if firstLine:# Skip first line
        firstLine = False
        continue
    if (_DATASET == 'enISEAR_V1'):
        vector_row = [int(row[3]),int(row[4]),int(row[5]),int(row[6]),int(row[7]),int(row[8]),int(row[9])]
    elif (_DATASET == 'enISEAR_V2'):
        vector_row = [int(row[3]),int(row[4]),int(row[5]),int(row[6]),int(row[7]),int(row[8]),int(row[9])]
    elif (_DATASET == 'enISEAR_V3'):
        vector_row = [int(row[3]),int(row[4]),int(row[5]),int(row[6]),int(row[7]),int(row[8])]
    vectors.append(vector_row)

vectors = np.array(vectors)

data_raw = pd.read_csv(DATASET, sep='\t')
classes_enISEAR = data_raw['Prior_Emotion']
sentence_enISEAR = data_raw['Sentence']
vectorizer = CountVectorizer()
sentence_enISEAR = vectorizer.fit_transform(sentence_enISEAR)

if (_DATASET == 'enISEAR_V1'):
    class_weight = {0: 1.131,
                    1: 1.000,
                    2: 1.903,
                    3: 5.107,
                    4: 2.019,
                    5: 3.338,
                    6: 3.171}
elif (_DATASET == 'enISEAR_V2'):
    print('not done yet')
    class_weight = {0: 999,
                    1: 999,
                    2: 999,
                    3: 999,
                    4: 999,
                    5: 999,
                    6: 999}
elif (_DATASET == 'enISEAR_V3'):
    class_weight = {0: 1.667,
                    1: 1.000,
                    2: 1.000,
                    3: 5.000,
                    4: 1.667,
                    5: 2.500}

def performCrossValidation(x_data, y_data):
    metrics_final = metrics.metrics(None, None, LABELS, 2)

    for seed in range(ROUNDS):
        np.random.seed(seed)
        kfold = KFold(n_splits=KFOLDS, shuffle=True, random_state=seed)
        for train, test in kfold.split(x_data, y_data):
            from keras import backend as K
            K.clear_session()
            classes_train = pd.concat([y_data[train], pd.get_dummies(y_data[train])],axis=1).drop(['Prior_Emotion'],axis=1)
            classes_test = pd.concat([y_data[test], pd.get_dummies(y_data[test])],axis=1).drop(['Prior_Emotion'],axis=1)

            input_shape  = sentence_enISEAR.shape[1] # feature count
            print(input_shape)

            ####################################################################
            # Task 1 : Learn to predict appraisals from text
            ####################################################################
            print('Learning to predict dimensions from text')
            appraisal_predictor = Sequential()
            appraisal_predictor.add(Dense(7, input_shape=(input_shape ,), activity_regularizer=regularizers.l2(0.01)))
            appraisal_predictor.add(Activation('sigmoid'))
            appraisal_predictor.compile(loss='binary_crossentropy', metrics=['accuracy'], optimizer='adam')
            appraisal_predictor.fit(sentence_enISEAR[train], vectors[train], batch_size=BATCH_SIZE, epochs=EPOCHS_TA, verbose=VERBOSITY, class_weight=class_weight)

            # weights = [0.50, 0.51, 0.485, 0.485, 0.475, 0.475, 0.485]
            # weights = [0.51, 0.5125, 0.475, 0.475, 0.50, 0.4750, 0.495]
            weights = [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50]
            preds = appraisal_predictor.predict(sentence_enISEAR[test])
            predicted_appraisals = []
            for row in range(len(preds)):
                res = []
                for dim in range(len(DIMENSIONS)):
                    value = preds[row][dim]
                    if (value >= weights[dim]):
                        value = 1
                    else:
                        value = 0
                    res.append(value)
                predicted_appraisals.append(res)

            predicted_appraisals = np.array(predicted_appraisals)

            ####################################################################
            # Task 2 : Learn to predict emotions from appraisals
            ####################################################################
            print('Learning to predict emotions from dimensions')
            emotion_predictor = Sequential()
            emotion_predictor.add(Dense(7, input_shape=(7,), activity_regularizer=regularizers.l2(0.01)))
            emotion_predictor.add(Activation('softmax')) # Softmax regression
            emotion_predictor.compile(loss='categorical_crossentropy', metrics=['accuracy'], optimizer=OPTIMIZER)
            emotion_predictor.fit(x_data[train], classes_train, batch_size=BATCH_SIZE, epochs=EPOCHS_AE, verbose=VERBOSITY)

            predicted_emotions = []
            predictions = emotion_predictor.predict(predicted_appraisals)
            for i in range(len(predictions)):
                index = np.argmax(predictions[i])
                predicted_emotions.append(LABELS[index])

            rounding_decimals = 2
            metrics_fold = metrics.metrics(y_data[test], predicted_emotions, LABELS, rounding_decimals)
            metrics_fold.showResults()
            metrics_final.addIntermediateResults(y_data[test], predicted_emotions)

    print('\nFinal Result:')
    metrics_final.writeResults(EXPERIMENTNAME, SAVEFILE)
    return


performCrossValidation(vectors, classes_enISEAR)
