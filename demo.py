import argparse
import torch
import copy
import numpy as np

from sgm.modules.diffusionmodules.openaimodel import get_feature_dic
from scripts.demo.turbo import *
from utils import plot_mask
from seg_module import Segmodule


def demo(ckpt_path, output_path):
    st.title("Turbo Segmentation")
    
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    seg_module = Segmodule().to(device)
    seg_module.load_state_dict(torch.load(ckpt_path, map_location="cpu"), strict=True)
    
    head_cols = st.columns([1, 1, 1, 1])
    with head_cols[0]:
        version = st.selectbox("Model Version", list(VERSION2SPECS.keys()), 0)
        version_dict = VERSION2SPECS[version]

    with head_cols[1]:
        v_spacer(2)
        if st.checkbox("Load Model"):
            mode = "txt2img"
        else:
            mode = "skip"
    
    with head_cols[2]:
        v_spacer(2)
        if st.checkbox("Save img"):
            save_img = True
        else:
            save_img = False

    if mode != "skip":
        state = init_st(version_dict, load_filter=True)
        if state["msg"]:
            st.info(state["msg"])
        model = state["model"]
        load_model(model)

    # seed
    if "seed" not in st.session_state:
        st.session_state.seed = 0

    def increment_counter():
        st.session_state.seed += 1

    def decrement_counter():
        if st.session_state.seed > 0:
            st.session_state.seed -= 1

    with head_cols[3]:
        n_steps = st.number_input(label="number of steps", min_value=4, max_value=4)
    
    sampler = SubstepSampler(
        n_sample_steps=4,
        num_steps=1000,
        eta=1.0,
        discretization_config=dict(
            target="sgm.modules.diffusionmodules.discretizer.LegacyDDPMDiscretization"
        ),
    )
    sampler.n_sample_steps = n_steps
    default_prompt = "A cinematic shot of a baby racoon wearing an intricate italian priest robe."
    default_category = "racoon"
    prompt = st_keyup("Prompt for diffusion", value=default_prompt, debounce=300, key="interactive_text")
    category = st_keyup("Query category", value=default_category, debounce=30, key="text")
    

    cols = st.columns([1, 5, 1])
    if mode != "skip":
        with cols[0]:
            v_spacer(14)
            st.button("↩", on_click=decrement_counter)
        with cols[2]:
            v_spacer(14)
            st.button("↪", on_click=increment_counter)

        sampler.noise_sampler = SeededNoise(seed=st.session_state.seed)
        out = sample(
            model, sampler, H=512, W=512, seed=st.session_state.seed, prompt=prompt, filter=state.get("filter")
        )
        img = out[0]
        
        # get class embedding
        class_embedding, uc = get_cond(model, H=512, W=512, prompt=category)
        class_embedding = class_embedding['crossattn'][:, 1, :].unsqueeze(1)

        # seg_module
        pred_seg = seg_module(get_feature_dic(), class_embedding)[0]
        pred_prob = torch.sigmoid(pred_seg)
        pred_seg = torch.zeros_like(pred_prob, dtype=torch.float32)
        pred_seg[pred_prob > 0.5] = 1
        
        mask = pred_seg.cpu().numpy()
        mask = np.expand_dims(mask, 0)
        image_mask = plot_mask(img, mask, colors=[0, 255, 0], alpha=0.5, indexlist=[0]).reshape((512, 512, 3))
        output = np.concatenate([img, image_mask], axis = 1)
        with cols[1]:
            st.image(output)
            if save_img:
                Image.fromarray(output).save(f'{output_path}/{prompt}.png')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    ckpt_path = 'checkpoints/checkpoint_latest_DSFP.pth'
    output_path = 'outputs/txt2img'
    os.makedirs(output_path, exist_ok=True)
    demo(ckpt_path, output_path)
