# This makefile was created for a local Docker build of the metagenome distribution, but the DISTRIBUTION variable has been added for ease of use with other distributions that may need to be built locally in the future.

# The QIIME2_RELEASE should be changed to the current 20XX.REL epoch
QIIME2_RELEASE := 2024.5
DISTRIBUTION := metagenome

.PHONY: docker
docker:
	docker build \
		-t quay.io/qiime2/$(DISTRIBUTION):$(QIIME2_RELEASE) \
		-t quay.io/qiime2/$(DISTRIBUTION):latest \
		--build-arg QIIME2_RELEASE=$(QIIME2_RELEASE) docker
