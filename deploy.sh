#!/bin/bash

# Initialize git if not already initialized
if [ ! -d .git ]; then
    git init
fi

# Add all files
git add .

# Commit changes
echo "Enter commit message:"
read commit_message
git commit -m "$commit_message"

# Add GitHub remote if not exists
if ! git remote | grep -q 'origin'; then
    echo "Enter your GitHub repository URL:"
    read repo_url
    git remote add origin $repo_url
fi

# Push to GitHub
git push -u origin main

echo "Deployment complete!" 