# This makefile was created for a local Docker build of the metagenome distribution, but the DISTRO variable has been added for ease of use with other distributions that may need to be built locally in the future.

# The EPOCH should be changed to the current 20XX.REL epoch
EPOCH := 2024.5
DISTRO := metagenome

.PHONY: docker docker-workshop

docker:
	docker build \
		-f Dockerfile.base \
		-t quay.io/qiime2/$(DISTRO):$(EPOCH) \
		-t quay.io/qiime2/$(DISTRO):latest \
		--build-arg EPOCH=$(EPOCH) \
		--build-arg DISTRO=$(DISTRO) \
		--no-cache \
		.

docker-workshop:
	docker build \
		-f Dockerfile.workshop \
		-t quay.io/qiime2/$(DISTRO):$(EPOCH)-workshop \
		--build-arg EPOCH=$(EPOCH) \
		--build-arg DISTRO=$(DISTRO) \
		--no-cache \
		.
