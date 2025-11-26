# This makefile was created for a local Docker build of the moshpit distribution, but the DISTRO variable has been added for ease of use with other distributions that may need to be built locally in the future.

# The EPOCH should be changed to the current 20XX.REL epoch
EPOCH := 2024.10
DISTRO := moshpit

.PHONY: docker docker-workshop

docker:
	docker build \
		-f Dockerfile.base \
		-t quay.io/rachis/$(DISTRO):$(EPOCH) \
		-t quay.io/rachis/$(DISTRO):latest \
		--build-arg EPOCH=$(EPOCH) \
		--build-arg DISTRO=$(DISTRO) \
		--no-cache \
		.

docker-workshop:
	docker build \
		-f Dockerfile.workshop \
		-t quay.io/rachis/$(DISTRO)-workshop:$(EPOCH) \
		--build-arg EPOCH=$(EPOCH) \
		--build-arg DISTRO=$(DISTRO) \
		--no-cache \
		.
