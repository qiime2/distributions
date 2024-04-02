FROM continuumio/miniconda3:latest

ARG EPOCH
ARG DISTRO

ENV PATH /opt/conda/envs/qiime2-${DISTRO}-${EPOCH}/bin:$PATH
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV MPLBACKEND agg
ENV HOME /home/qiime2
ENV XDG_CONFIG_HOME /home/qiime2

RUN mkdir /home/qiime2
WORKDIR /home/qiime2

RUN conda update -q -y conda
RUN conda install -q -y wget
RUN apt-get install -y procps

COPY ${EPOCH}/${DISTRO}/released/qiime2-${DISTRO}-ubuntu-latest-conda.yml released-env.yml
RUN conda env create -n qiime2-${DISTRO}-${EPOCH} --file released-env.yml \
 && conda clean -a -y \
 && chmod -R a+rwx /opt/conda \
 && rm released-env.yml

RUN /bin/bash -c "source activate qiime2-${DISTRO}-${EPOCH}"
ENV CONDA_PREFIX /home/qiime2/.conda/qiime2-${DISTRO}-${EPOCH}/
RUN qiime dev refresh-cache
RUN echo "source activate qiime2-${DISTRO}-${EPOCH}" >> $HOME/.bashrc
RUN echo "source tab-qiime" >> $HOME/.bashrc

# Important: let any UID modify these directories so that
# `docker run -u UID:GID` works
RUN chmod -R a+rwx /home/qiime2

# TODO: update this to point at the new homedir defined above. Keeping this
# for now because this will require an update to the user docs.
VOLUME ["/data"]
WORKDIR /data