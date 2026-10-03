// Shared material helpers for stops: the black-and-white fade used by the transition.
// Each stop keeps one { value: 0..1 } uniform and hands it to every material it owns.

// For custom shaders: declare the uniform and wrap the final colour in toGrey().
export const GREY_GLSL = /* glsl */`
uniform float uGrey;
vec3 toGrey(vec3 c) { return mix(c, vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), uGrey); }`;

// For built-in three.js materials (MeshBasicMaterial and friends): greys the colour
// right after the texture is applied, so photos and video frames fade too.
export function addGrey(material, uniform) {
  material.onBeforeCompile = shader => {
    shader.uniforms.uGrey = uniform;
    shader.fragmentShader = GREY_GLSL + '\n' + shader.fragmentShader.replace(
      '#include <map_fragment>', '#include <map_fragment>\n  diffuseColor.rgb = toGrey(diffuseColor.rgb);');
  };
  material.customProgramCacheKey = () => 'grey';
  return material;
}
