import argparse
import logging
import os

import h5py
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models
from torchvision import transforms, utils
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
from skimage import io, transform


parser = argparse.ArgumentParser()
parser.add_argument('--model', default='resnet34',
                    choices=['resnet18', 'resnet34'], help='ResNet Version')
parser.add_argument('--save_name', default='models/class_pov',
                    help='Base dir name to keep saved model and log')
parser.add_argument('--label', default='pov_label', choices=[
                    'pov_label', 'pop_label', 'bmi_label'], help='Label used for training')
parser.add_argument('--lr', type=float, default=1e-3,
                    help='Training learning rate')
parser.add_argument('--batch_size', type=int, default=256,
                    help='Training batch size')
parser.add_argument('--num_epochs', type=int, default=100,
                    help='Training number of epochs')
parser.add_argument('--pretrained', action='store_true',
                    help='Use pretrained Imagenet weights')
args = parser.parse_args()

if not os.path.exists(args.save_name):
    os.makedirs(args.save_name)
logging.basicConfig(filename=args.save_name + '/log', level=logging.DEBUG)
writer = SummaryWriter(args.save_name)


class ImgDataset(Dataset):
    def __init__(self, df, device):
        self.img_paths = df['img_path_224x224'].to_numpy()
        self.targets = df[args.label].to_numpy()
        self.device = device

    def __len__(self):
        return self.img_paths.shape[0]

    def __getitem__(self, idx):
        image = io.imread(self.img_paths[idx])
        image_tensor = torch.from_numpy(image)
        image_tensor = image_tensor.permute(2, 0, 1).float()
        target = torch.Tensor(np.array([self.targets[idx]]))
        return image_tensor, target


def create_model():
    if args.model == 'resnet18':
        model = models.resnet18(pretrained=args.pretrained)
    elif args.model == 'resnet34':
        model = models.resnet34(pretrained=args.pretrained)
    model.fc = nn.Linear(512, 2)  # num_classes is 2
    return model


def train(model, device, train_loader, optimizer, criterion, epoch):
    model.train()
    for batch_idx, (data, target) in enumerate(train_loader):
        data, target = data.to(device), target.to(device)
        optimizer.zero_grad()
        output = model(data)
        target = target.view(-1).long()
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
        pred = output.argmax(dim=1, keepdim=True)
        correct = pred.eq(target.view_as(pred).long()).sum().item()
        if batch_idx % 5 == 0:
            logging.info('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}\tAccuracy: {}/{} ({:.0f}%)'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item(),
                correct, 256, 100 * correct / float(256)))
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}\tAccuracy: {}/{} ({:.0f}%)'.format(
                epoch, batch_idx * len(data), len(train_loader.dataset),
                100. * batch_idx / len(train_loader), loss.item(),
                correct, 256, 100 * correct / float(256)))
            writer.add_scalar('Loss/train', loss.item(),
                              epoch * len(train_loader) + batch_idx)
            writer.add_scalar('Accuracy/train', correct /
                              float(256), epoch * len(train_loader) + batch_idx)


def test(model, device, test_loader, criterion, epoch):
    model.eval()
    test_loss = 0
    total = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            target = target.view(-1).long()
            total += target.size(0)
            output = model(data)
            # get the index of the max log-probability
            pred = output.argmax(dim=1, keepdim=True)
            correct += pred.eq(target.view_as(pred).long()).sum().item()

    acc = correct / total
    logging.info('\nTest set: Accuracy: {}/{} ({:.4f}%)\n'.format(
        correct, total, 100. * acc))
    print('\nTest set: Accuracy: {}/{} ({:.4f}%)\n'.format(
        correct, total, 100. * acc))
    writer.add_scalar('Accuracy/test', acc, epoch * total)
    return acc


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    print('Getting the clusters')
    train_f = open('/kaggle/input/train-val/train_clusters_ke.txt', 'r')
    val_f = open('/kaggle/input/train-val/val_clusters_ke.txt', 'r')
    train_clusters = [x[:-1] for x in train_f.readlines()]
    val_clusters = [x[:-1] for x in val_f.readlines()]
    train_f.close()
    val_f.close()

    print('Preparing the dataloader')
    df = pd.read_csv('/kaggle/input/final-data/final_data_200.csv')
    train_df = df.loc[df['unique_cluster'].isin(train_clusters)]
    train_df = train_df.sample(frac=1).reset_index(drop=True)
    val_df = df.loc[df['unique_cluster'].isin(val_clusters)]
    val_df = val_df.sample(frac=1).reset_index(drop=True)

    train_dataset = ImgDataset(train_df, device)
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, num_workers=2)
    val_dataset = ImgDataset(val_df, device)
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, num_workers=2)

    model = create_model()
    if torch.cuda.device_count() > 1:
        print(f"Using {torch.cuda.device_count()} GPUs!")
        model = nn.DataParallel(model)  # Wrap the model for multi-GPU training
    model.to(device)

    criterion = torch.nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-6)

    print('Starting training')
    best_acc = 0.
    for epoch in range(1, args.num_epochs+1):
        train(model, device, train_loader, optimizer, criterion, epoch)
        acc = test(model, device, val_loader, criterion, epoch)
        if acc >= best_acc:
            best_acc = acc
            # Note: When using DataParallel, save the model.module.state_dict()
            torch.save(model.module.state_dict() if isinstance(
                model, nn.DataParallel) else model.state_dict(), args.save_name + '/model.hdf5')
            logging.info("\nSaved model with Acc: {:.4f}\n".format(best_acc))
            print("\nSaved model with Acc: {:.4f}\n".format(best_acc))

    logging.info("\nBest Acc: {:.4f}\n".format(best_acc))
    print("\nBest Acc: {:.4f}\n".format(best_acc))


if __name__ == "__main__":
    main()
