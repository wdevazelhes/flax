
from flax.core import Scope, init, apply, unfreeze, lift
from typing import Sequence, Callable

from flax import nn

import jax
from jax import lax, random, numpy as jnp

from typing import Any
from functools import partial, wraps

Array = Any


def weight_std(fn, kernel_name='kernel', eps=1e-8):
  def std(target):
    params = target['param']
    assert kernel_name in params
    kernel = params[kernel_name]
    redux = tuple(range(kernel.ndim - 1))
    norm = jnp.square(kernel).sum(redux, keepdims=True)
    std_kernel = kernel / jnp.sqrt(norm + eps)
    params[kernel_name] = std_kernel
    return target

  # transform handles a few of nasty edge cases here...
  # the transformed kind will be immutable inside fn
  # this way we avoid lost mutations to param
  # transform also avoids accidental reuse of rngs
  # and it makes sure that other state is updated correctly (not twice during init!)

  @wraps(fn)
  def wrapper(scope, *args, **kwargs):
    is_init = not scope.has_variable('param', kernel_name)
    lift_std = lift.transform(std, 'param', init=is_init)
    fn_p = partial(fn, **kwargs)
    return lift_std(scope, fn_p, *args)
    
  return wrapper

def mlp(scope: Scope, x: Array,
        sizes: Sequence[int] = (2, 4, 1),
        act_fn: Callable[[Array], Array] = nn.relu):
  std_dense = weight_std(partial(nn.dense, kernel_init=nn.initializers.normal(stddev=1e5)))
  # hidden layers
  for size in sizes[:-1]:
    x = scope.child(std_dense, prefix='hidden_')(x, size)
    # x = act_fn(x)

  # output layer
  return scope.child(nn.dense, 'out')(x, sizes[-1])


x = random.normal(random.PRNGKey(0), (1, 4,))
y, params = init(mlp)(random.PRNGKey(1), x)
print(y)
print(jax.tree_map(jnp.shape, unfreeze(params)))