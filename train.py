import time
import argparse
import numpy as np
import torch
from deeprobust.graph.defense import GCN
from prognn import ProGNN # copy from deeprobust.graph.defense
from deeprobust.graph.data import Dataset, PrePtbDataset
from deeprobust.graph.utils import preprocess, encode_onehot, get_train_val_test
from bigclam import train_labels
from scipy import sparse

# Training settings
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true',
        default=False, help='debug mode')
parser.add_argument('--only_gcn', action='store_true',
        default=False, help='test the performance of gcn without other components')
parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='Disables CUDA training.')
parser.add_argument('--seed', type=int, default=15, help='Random seed.')
parser.add_argument('--lr', type=float, default=0.01,
                    help='Initial learning rate.')
parser.add_argument('--weight_decay', type=float, default=5e-4,
                    help='Weight decay (L2 loss on parameters).')
parser.add_argument('--hidden', type=int, default=16,
                    help='Number of hidden units.')
parser.add_argument('--dropout', type=float, default=0.5,
                    help='Dropout rate (1 - keep probability).')
parser.add_argument('--dataset', type=str, default='cora',
        choices=['cora', 'cora_ml', 'citeseer', 'polblogs', 'pubmed'], help='dataset')
parser.add_argument('--attack', type=str, default='meta',
        choices=['no', 'meta', 'random', 'nettack'])
parser.add_argument('--ptb_rate', type=float, default=0.05, help="noise ptb_rate")
parser.add_argument('--epochs', type=int,  default=400, help='Number of epochs to train.')
parser.add_argument('--alpha', type=float, default=5e-4, help='weight of l1 norm')
parser.add_argument('--beta', type=float, default=1.5, help='weight of nuclear norm')
parser.add_argument('--gamma', type=float, default=1, help='weight of l2 norm')
parser.add_argument('--lambda_', type=float, default=0, help='weight of feature smoothing')
parser.add_argument('--phi', type=float, default=0, help='weight of symmetric loss')
parser.add_argument('--inner_steps', type=int, default=2, help='steps for inner optimization')
parser.add_argument('--outer_steps', type=int, default=1, help='steps for outer optimization')
parser.add_argument('--lr_adj', type=float, default=0.01, help='lr for training adj')
parser.add_argument('--symmetric', action='store_true', default=False,
            help='whether use symmetric matrix')
parser.add_argument('--pre', type=str, default='', help='preprocessing with bigCLAM algorithm')

args = parser.parse_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()
device = torch.device("cuda" if args.cuda else "cpu")
if args.cuda:
    torch.cuda.manual_seed(args.seed)
if args.ptb_rate == 0:
    args.attack = "no"

print(args)

# Here the random seed is to split the train/val/test data,
# we need to set the random seed to be the same as that when you generate the perturbed graph
# but now change the setting from nettack to prognn which directly loads the prognn splits
# data = Dataset(root='/tmp/', name=args.dataset, setting='nettack', seed=15)
data = Dataset(root='/tmp/', name=args.dataset, setting='prognn')
adj, features, labels = data.adj, data.features, data.labels
adj2, features2, labels2 = data.adj, data.features, data.labels
features2 = data.features
print("LABELS", labels)
idx_train, idx_val, idx_test = data.idx_train, data.idx_val, data.idx_test

#資料前處理
if args.attack == 'no':
    perturbed_adj = adj

if args.attack == 'random':
    from deeprobust.graph.global_attack import Random
    # to fix the seed of generated random attack, you need to fix both np.random and random
    # you can uncomment the following code
    # import random; random.seed(args.seed)
    # np.random.seed(args.seed)
    attacker = Random()
    n_perturbations = int(args.ptb_rate * (adj.sum()//2)) #擾動率*graph所有可以連接的邊
    attacker.attack(adj, n_perturbations, type='add') #加邊
    perturbed_adj = attacker.modified_adj

if args.attack == 'meta' or args.attack == 'nettack':
    # 生成 data 到 /tmp/
    perturbed_data = PrePtbDataset(root='/tmp/',
            name=args.dataset,
            attack_method=args.attack,
            ptb_rate=args.ptb_rate)
    perturbed_adj = perturbed_data.adj
    perturbed_adj2 = perturbed_data.adj
    if args.attack == 'nettack':
        idx_test = perturbed_data.target_nodes
        print("[INFO] idx_test", idx_test)

## 使用BigCLAM做資料前處理，再將切出來的sub-graph分別丟入ProGNN中做訓練
if args.pre == 'big':
    print("Run BigCLAM algorithm to split dataset...")
    
        
np.random.seed(args.seed)
torch.manual_seed(args.seed)

model = GCN(nfeat=features.shape[1],
            nhid=args.hidden,
            nclass=labels.max().item() + 1,
            dropout=args.dropout, device=device)

if args.only_gcn:
    print('---------- before preprocess ----------')
    print('perturbed_adj: ', type(perturbed_adj))
    perturbed_adj, features, labels = preprocess(perturbed_adj, features, labels, preprocess_adj=False, sparse=True, device=device)
    print('---------- after preprocess ----------')
    print('perturbed_adj: ', type(perturbed_adj))
    model.fit(features, perturbed_adj, labels, idx_train, idx_val, verbose=True, train_iters=args.epochs)
    model.test(idx_test)
elif args.pre == 'big':
    labels_t = train_labels(perturbed_adj.toarray(), 7, iterations=100)
    print(labels_t, len(labels_t), labels, len(labels))
    
    #print(features, type(features))
    perturbed_adj, features, labels_t = preprocess(perturbed_adj, features, labels_t, preprocess_adj=False, device=device)
    #print(features, type(features))
    
    #features = features.cpu().numpy()
    #print(features)
    perturbed_adj2, features2, labels = preprocess(perturbed_adj2, features2, labels, preprocess_adj=False, device=device)

    prognn = ProGNN(model, args, device)
    prognn.fit(features, perturbed_adj, labels_t, idx_train, idx_val)
    prognn.test(features, labels_t, idx_test)
    
else:
    perturbed_adj, features, labels = preprocess(perturbed_adj, features, labels, preprocess_adj=False, device=device)
    print("perturbed adj is", perturbed_adj, "label", labels, "features", features)
    prognn = ProGNN(model, args, device)
    prognn.fit(features, perturbed_adj, labels, idx_train, idx_val)
    prognn.test(features, labels, idx_test)

