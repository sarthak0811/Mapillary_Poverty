# Mapillary_Poverty
Improving the initial work done by sustainlab-group. Improving the accuracy for predicting Poverty levels in Kenya using Augmented data and Hierarchical GCN.

Data: All the npy files that will be required.

mapillary_with_augmentation: 
The original code can be found at https://github.com/sustainlab-group/mapillarygcn/tree/master
I made some changes to remove dependencies of previous versions of various libraries. The images were also augmented to increase the dataset size and add some noise for better training.

working_seamseg_main:
Working code of seamseg library. The original code can be found at https://github.com/mapillary/seamseg/tree/main

The Virtual-Environment file helps in creating an environment where the original codes can be run without any dependency issues.
The augmentation_working file runs the mapillary_with_augmentation code and saves outputs as an npy file.
The seamseg file runs the seamless scene segmentation model.
The wandb file was for testing various parameters of the gcn.
The best-gcn-embed file runs the final code.

Process: The main working can be understood from the Guthub repo of sustain-lab group (above link). The following changes were made to improve the accuracies:
  1) Augmenting the data for clusters that have very few images.
  2) The original model by SustainLab works with a Graph-level prediction model, which only works at an Intra-Cluster Level. To better understand the Inter-Cluster relationships, a super-graph is made where each cluster is one of the original graphs. Features from the final embed layer were extracted for each graph, which become the node features for the super-graph. the adjacency matrix is constructed by using the distance between each cluster centre.
     
![Alt text](./network.png?raw=true "Title")
